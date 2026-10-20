# RAG 问答链路设计文档

本文档描述「上传文档 → 向量入库 → 多轮问答」中 **问答环节** 的完整设计，与当前代码实现一致。

---

## 1. 目标与原则

| 原则 | 说明 |
|------|------|
| 上下文方案 A | Redis 滑动窗口保存最近 N 轮；改写与回答均使用该上下文 |
| 落库策略 | **Redis + MySQL 双写（同步）**：每条 user/assistant 消息同时写 Redis 与 `chat_messages` |
| 双路召回 | 每个变式问句：**向量路 20 条 + BM25 稀疏路 20 条**（Hybrid 混合检索） |
| 多层 RRF | 问内 RRF → 跨问 RRF → 可选 Rerank → LLM |
| 用户隔离 | Milvus / MySQL 检索均按 `user_id` 过滤 |

---

## 2. 端到端流程

```text
POST /api/chat/query { query, session_id?, file_ids? }
        │
        ▼
┌───────────────────────────────────────┐
│ 1. 加载上下文（Redis；空则 DB 回填）      │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 2. 查询理解 query_understanding         │
│    intent: qa | chitchat | unclear |  │
│            out_of_scope                 │
│    standalone_query（独立检索问句）    │
└───────────────────────────────────────┘
        │
        ├─ 非 qa ──► reply_hint 直接回复 ──► 落库 ──► 返回
        │
        ▼
┌───────────────────────────────────────┐
│ 3. 问句变式 query_expand (N 条)        │
└───────────────────────────────────────┘
        │
        ▼
  对每个变式 Qi:
┌───────────────────────────────────────┐
│ 4a. 向量路 Milvus top 20              │
│     embed_text(Qi) → search           │
│ 4b. BM25 稀疏路 top 20                 │
│     MySQL 语料 → BM25Okapi 打分       │
│ 4c. 问内 RRF → 每问最多 15 条         │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 5. 跨问 RRF → 最终 15 条              │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 6. 可选 DashScope TextReRank → Top-K │
│    (RERANK_ENABLED，默认关闭)         │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 7. rag.generate_answer (qwen-max)    │
└───────────────────────────────────────┘
        │
        ▼
  Redis + MySQL 双写 user/assistant
        │
        ▼
  ChatQueryResponse { answer, sources, session_id }
```

---

## 3. RRF 公式

对文档 \(d\) 在多路排序列表中的排名 \(rank_i\)（从 1 开始）：

\[
RRF(d) = \sum_i \frac{1}{k + rank_i}
\]

默认 `RRF_K=60`。去重键：`file_id + chunk_index` 或 Milvus `id`。

---

## 4. 文件清单与职责

### 4.1 API 层

| 文件 | 职责 |
|------|------|
| `backend/app/api/chat.py` | 问答入口；会话校验；`asyncio.to_thread` 调用同步 RAG 流水线；Redis/DB 双写；修复 `create_session` 参数顺序 |

### 4.2 检索与融合

| 文件 | 职责 |
|------|------|
| `backend/app/core/retrieval_pipeline.py` | **主编排**：理解 → 变式 → 双路召回 → 多层 RRF → 返回 chunks |
| `backend/app/core/query_understanding.py` | 意图识别 + 多轮改写为 `standalone_query` |
| `backend/app/core/query_expand.py` | 生成 N 个检索变式问句 |
| `backend/app/core/fusion.py` | `rrf_fuse()` 通用 RRF 实现 |
| `backend/app/core/keyword_retrieval.py` | **BM25 稀疏路**：MySQL 语料 + `rank_bm25.BM25Okapi` + jieba 分词 |
| `backend/app/core/milvus_service.py` | **向量路**：`search(user_id, embedding, top_k, file_ids?)` |
| `backend/app/core/rag.py` | `embed_text()` 查询向量；`generate_answer()` LLM 生成答案 |

### 4.3 基础设施

| 文件 | 职责 |
|------|------|
| `backend/app/core/redis_manager.py` | `session:{id}:context` 滑动窗口；`MAX_CONTEXT_TURNS` / `CONTEXT_CACHE_TTL` |
| `backend/app/core/llm_utils.py` | LLM 返回文本规范化 |
| `backend/app/models/chat.py` | `chat_sessions` / `chat_messages`；`sources` JSON |
| `backend/app/models/document.py` | `search_chunks_by_user()` 拉取用户已嵌入切片供词面检索 |
| `backend/app/schemas/chat.py` | `ChatQueryRequest`（含可选 `file_ids`） |

### 4.4 与入库链路的关系

| 文件 | 关系 |
|------|------|
| `backend/app/tasks/file_processing.py` | 解析 → 切片 → LLM 增强 → `embed_document` → Milvus；**问答检索依赖此链路产出的向量与 `document_chunks`** |

---

## 5. 数据库与 Redis 使用

### MySQL

- **`chat_sessions`**：会话元数据
- **`chat_messages`**：`role`, `content`, **`sources` JSON**（最终引用切片）
- **`document_chunks`** + **`file_metadata`**：词面检索 JOIN；`is_embedded=1` 过滤

### Redis

- Key: `session:{session_id}:context`
- Value: JSON 数组 `[{role, content, timestamp, sources?}, ...]`
- TTL: `CONTEXT_CACHE_TTL`（默认 1800s）
- 条数: `MAX_CONTEXT_TURNS * 2`（默认 3 轮 = 6 条完整问答）
- Token: `MAX_CONTEXT_TOKENS`（默认 20000）；超限时用快模型压缩较早轮次，保留最近一轮全文

### Milvus

- 实体: `user_id`, `file_id`, `chunk_index`, `embedding`, `chunk_text`, `metadata`
- 检索: IP 相似度 + `user_id` 表达式过滤

---

## 6. 环境变量（`.env`）

```env
MAX_CONTEXT_TURNS=3
MAX_CONTEXT_TOKENS=20000
CONTEXT_CACHE_TTL=1800
QUERY_EXPAND_N=3
RETRIEVE_TOP_K_PER_PATH=20
RRF_PER_QUERY=15
RRF_FINAL=15
ANSWER_TOP_K=10
RRF_K=60
RERANK_ENABLED=false
RERANK_MODEL=gte-rerank-v2
RERANK_MAX_DOC_CHARS=6000
DASHSCOPE_ANSWER_MODEL=qwen-max
MILVUS_ENABLED=true
DASHSCOPE_API_KEY=...

# RAG 分阶段可观测日志（问答侧）
RAG_TRACE_ENABLED=true
RAG_TRACE_DIR=logs
RAG_TRACE_FULL=false
```

问答请求会按 `request_id` 写入 `logs/rag_trace.jsonl`（控制台同时打摘要），阶段包括：`request_start` → `query_understanding` → `query_expand` → `vector_search` / `bm25_search` → `rrf_per_query` → `rrf_final` → `rerank`（若开启）→ `generate_answer` → `request_end`。

---

## 7. API 说明

### POST `/api/chat/query`

**请求体**

```json
{
  "query": "Transformer 的注意力头数是多少？",
  "session_id": "可选，不传则新建",
  "file_ids": [7]
}
```

**响应**

```json
{
  "answer": "...",
  "sources": [
    { "content": "...", "score": 0.032, "metadata": { "page_numbers": [3] } }
  ],
  "session_id": "uuid"
}
```

---

## 8. Hybrid 混合检索（向量 + BM25）

| 路径 | 实现 | 每问条数 | 说明 |
|------|------|----------|------|
| **稠密向量路** | `embed_text` + Milvus HNSW（IP） | 20 | 语义相似度 |
| **BM25 稀疏路** | MySQL 语料 + `BM25Okapi` | 20 | 关键词 / 词面匹配（Okapi BM25） |

两路经 **问内 RRF** 融合为 15 条，再经 **跨问 RRF** → 最终 15 条 → LLM。这是标准 **Hybrid Retrieval** 结构。

### 8.1 BM25 稀疏路实现细节

**流程**（`keyword_retrieval.py` → `bm25_search`）：

1. **MySQL**：`search_chunks_by_user` 拉取用户已嵌入切片（候选池，默认最多 `BM25_CANDIDATE_LIMIT=2000`）。
2. **分词**：问句与每个 `chunk_text` 用 **jieba**（`BM25_USE_JIEBA=true`）切词；失败时回退简单规则。
3. **索引与打分**：内存构建 `BM25Okapi(corpus_tokens)`，对问句 token 算 BM25 分（默认 k1=1.5, b=0.75）。
4. **排序**：取 top 20，`metadata.retrieval = "bm25"`。

> MySQL **只提供语料**，不在库内做 BM25 排序；索引按请求在内存构建（适合当前个人/中小规模文档库）。

### 8.2 与 Elasticsearch BM25 的差异

| | 当前实现 | ES / OpenSearch |
|--|---------|-----------------|
| 算法 | Okapi BM25（rank_bm25） | BM25（同类） |
| 索引 | 每次查询内存建索引 | 持久倒排索引 |
| 规模 | 建议单用户候选 ≤ 2000 切片 | 百万级+ |
| 与向量融合 | RRF | 同样可 RRF |

数据量增大后，可将 `bm25_search` 内部替换为 ES BM25，**RRF 流水线无需改动**。

### 8.3 环境变量

```env
BM25_USE_JIEBA=true
BM25_CANDIDATE_LIMIT=2000
RETRIEVE_TOP_K_PER_PATH=20
RRF_PER_QUERY=15
RRF_FINAL=15
RRF_K=60
```

---

## 9. 后续扩展

| 项 | 说明 |
|----|------|
| Rerank | 已接入：`RERANK_ENABLED=true` 时走 `app.core.reranker.dashscope_rerank`（TextReRank，默认 `gte-rerank-v2`；失败回退 RRF 截断） |
| 稀疏索引 | 数据量大时可改为 Elasticsearch BM25 + 持久倒排，RRF 接口不变 |
| 异步落库 | 当前为同步双写；若 QPS 高可改为 Redis 主写 + 后台 flush |
| 前端 | 可接入 `file_ids` 限定问答范围；加载 `/api/chat/history` 恢复会话 |

---

## 10. 调试建议

1. 确认文件 `status=processed` 且 Milvus 有向量  
2. 看日志中 `standalone_query` 与变式列表是否合理  
3. 对比向量路与词面路命中是否互补  
4. `sources` 中 `metadata.retrieval` 为 `vector` 或 `bm25`

---

*文档版本：与 backend 问答实现同步（双路 20 + 多层 RRF + Redis 方案 A + 同步双写）*
