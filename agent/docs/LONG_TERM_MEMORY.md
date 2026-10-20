# 长期记忆（LTM）完整方案

面向本仓库：Agent 短期窗口记忆已存在；RAG 文档在 `document_vectors`。  
长期记忆是 **跨会话、按用户** 的稳定事实/偏好，不要和文档切片混库。

---

## 0. 先回答：要不要新弄一个 `milvus_service.py`？

**不要把长期记忆塞进现有 `backend/app/core/milvus_service.py` 的同一张 Collection。**

| | 现有 `MilvusService` | 长期记忆 |
|--|---------------------|----------|
| Collection | `document_vectors` | **新建** `user_memories`（名可配置） |
| 主键语义 | `user_file_chunk` | `mem_{user}_{uuid}` |
| 过滤 | `user_id` + `file_id` | `user_id` + `source` + `status` + 时间 |
| 文本 | 文档 chunk | 一条提炼事实（短） |
| 删除 | 按文件/用户清文档 | 按记忆 id / 过期 / 覆盖 |

现有类的 `insert_vectors(user_id, file_id, chunks)`、`search(..., file_ids=)` **绑死了文件切片模型**。硬加字段会：

- 检索时文档和「用户姓张」混在一起  
- `file_id` 对对话记忆无意义（只能填 0 污染过滤）  
- 无法表达过期、来源、superseded  

**推荐落地形态（二选一，倾向 A）：**

**A. 新文件 + 共用连接（推荐）**

- 保留 `milvus_service.py` 只管 RAG  
- 新增 `backend/app/core/memory_milvus_service.py`（或 `agent` 侧适配器调 backend）  
- **同一 Milvus 实例/Lite 文件**，**另一个 Collection**  
- 连接（`connections.connect`）可抽一小段共享，避免两套 URI；不要复制整份 RAG 逻辑  

**B. 在 `MilvusService` 里加第二套 Collection 方法**

- 一个类两个 Collection，文件会迅速膨胀，RAG/记忆发布节奏绑死  
- 仅当团队强烈要求「一个 milvus 入口」时用  

**不要：** 改现有 schema 往 `metadata` JSON 里塞记忆（查不准、权限和过期都别扭）。

结论：**新 Collection + 新服务类（A）**；不是再造一个无关的 Milvus 集群，也不是覆盖 `milvus_service.py`。

---

## 1. 和现有两层记忆怎么叠

```text
一次提问
  ├─ 短期（已实现 SessionMemoryStore）
  │    近 3 轮对话骨架 + 更早增量摘要；进程内存；session_id
  ├─ 长期（本方案）
  │    按 user_id 向量检索 Top-K 条事实；跨登录、跨 session
  └─ RAG 文档（现有 document_vectors）
       用户上传的文件切片；按 user_id + file_id
```

| 层 | 存什么 | 生命周期 | 读 |
|----|--------|----------|----|
| 短期 | 原对话/工具过程 | 会话；现内存，建议后补 MySQL | 每轮直接拼 prompt |
| 长期 | 提炼后的事实、偏好、承诺 | 用户级，可过期 | **按需检索**，不是每次全塞 |
| RAG | 文档原文块 | 随文件增删 | 问答检索；与 LTM 分开召回再融合 |

短期解决「这框里刚说的」；长期解决「这个人上周说过敏」；RAG 解决「文件里怎么写的」。

---

## 2. 存什么（写入内容约束）

只存 **可独立理解的短事实**，例如：

- 偏好：「用户希望回答用中文、代码带注释」  
- 档案：「用户所在时区 Asia/Shanghai」（需用户说过或明确设置）  
- 项目上下文：「当前在做 RAG-FOR-BEGINNERS 的 Agent 模块」（可过期）  
- 从 RAG **提炼**的稳定结论（可选，`source=rag_digest`），不是整段 chunk  

**不存：** 整段聊天、工具 Observation 原文、一次性计算结果、文档全文。

每条建议 ≤ 200～400 字，一条一义。

---

## 3. Collection 设计（`user_memories`）

建议字段：

| 字段 | 类型 | 用途 |
|------|------|------|
| `id` | VARCHAR PK | `u{user_id}_m{uuid}` |
| `user_id` | INT64 | **强制隔离**，检索 expr 必带 |
| `source` | VARCHAR | `agent_dialog` / `user_explicit` / `rag_digest` / `profile` |
| `status` | VARCHAR | `active` / `superseded` / `expired` |
| `text` | VARCHAR | 记忆正文 |
| `embedding` | FLOAT_VECTOR | 与现网 embedding 同模型同维度（如 1024） |
| `created_at` | INT64 | unix 秒，及时性 |
| `updated_at` | INT64 | |
| `expires_at` | INT64 | 0 = 永不过期；档案类可 0，项目上下文 30～90 天 |
| `salience` | FLOAT | 0～1，显式「请记住」给高分 |
| `session_id` | VARCHAR | 溯源，可空 |
| `file_id` | INT64 | 仅 rag_digest 有意义，否则 0 |
| `metadata` | JSON | 证据摘要、冲突指向 `supersedes_id` 等 |

索引：`embedding` HNSW + IP（与 RAG 一致便于同一套 embed）。  
过滤：`user_id == X and status == "active" and (expires_at == 0 or expires_at > now)`。

MySQL 可选镜像表（便于后台改、审计、无向量的精确查）：`id, user_id, text, status, ...`。向量以 Milvus 为准，元数据以 MySQL 为准也可以——小流量可先 **只 Milvus**。

---

## 4. 代码怎么拆（实现时）

```text
backend/app/core/milvus_service.py      # 不动职责：只 document_vectors
backend/app/core/memory_milvus_service.py  # 新：user_memories CRUD + search
agent/memory/long_term.py                 # Agent 侧：retrieve / extract / upsert 门面
agent/memory/long_term_extract.py         # 终答后抽事实（fast 模型）
```

`memory_milvus_service.py` 方法建议：

- `ensure_collection()`  
- `upsert(user_id, text, embedding, source, ...)`  
- `search(user_id, query_embedding, top_k, sources=None)` — **内部写死 user_id 过滤**  
- `mark_superseded(user_id, id)` / `expire_due()`  
- `delete_by_user(user_id)` 注销用  

不要让 Agent 直接拼 Milvus expr 字符串。

---

## 5. 何时写入（更新）

**主路径：一轮 Agent 正常结束之后（有 Final Answer），异步抽取。**  
不要每个提问、每个工具步都写。

| 触发 | 行为 |
|------|------|
| 用户明确「记住/以后都要…」 | 立刻写，`source=user_explicit`，`salience` 高 |
| 对话成功结束 | 后台任务：用 fast 模型从「本轮用户话 + 终答 + 可选摘要」抽 0～3 条；没有新事实就 **空列表直接返回** |
| RAG 文件处理完成 | 可选：对文档摘要抽「用户知识库里关于 X 的稳定信息」，`source=rag_digest` + `file_id`；文件删除时同步删/过期这些记忆 |
| 定时（每天一次即可） | 把 `expires_at < now` 标 `expired`；合并极度相似的 active 条（可选） |

抽取 prompt 约束：只输出 JSON 列表；禁止把助手猜测写成记忆；与已有 Top 记忆重复则 `skip` 或 `supersede`。

写入前可先 **同用户检索** 该条候选：相似度很高 → 更新 `updated_at` 或标旧为 superseded 再插新，避免刷屏重复。

---

## 6. 何时读取（调用）

**每个提问可以检索，但不等于每次都塞进模型。**

建议策略（小流量够用）：

1. 用户已登录且有 `user_id`  
2. 用 **当前问题**（可加短期摘要一句）做 embedding  
3. `search(user_id, ..., top_k=5)`，只要 `active` 且未过期  
4. 分数过低则丢弃  
5. 拼进 prompt 单独一节：`## 长期记忆（可能过时，与本轮冲突时以本轮+较新记忆为准）`  
6. 闲聊且检索为空：不加该节  

**不要**把该用户全部长期记忆列出（会膨胀、过时条目干扰）。  
ReAct / Plan-Execute **共用同一 retrieve**，放在 `MainAgent.arun` 开头一次即可，不要每个 step 查一次。

是否「每个提问都查」：可以每次都 **检索**（一次向量查询很轻），但 **注入** 仅 Top-K 且可跳过空结果。这不是「每次更新」。

---

## 7. 权限

- 所有 search/insert/delete 的 `user_id` 来自 **登录态**，禁止请求体指定他人 id  
- 工具若暴露「查记忆」，签名里不要让模型选 user_id  
- RAG 与 LTM 检索都是 `user_id == 当前用户`，互不读取对方文档/记忆  

---

## 8. 信源与及时性

| source | 默认过期 | 冲突时权重 |
|--------|----------|------------|
| `user_explicit` | 不过期，除非用户改口 | 最高 |
| `agent_dialog` | 90 天可配 | 中，比文档口语更新但可能幻觉 |
| `rag_digest` | 随 file 删除而删；否则较长 | 以文件为准，文件更新应重抽 |
| `profile` | 不过期 | 高（若来自设置页） |

Prompt 里带上 `source` + `updated_at`，方便模型判断新旧。

---

## 9. 冲突怎么处理

三层，由稳到活：

1. **库内：** 新条写入若与旧条高相似且同 `user_id`：旧 `status=superseded`，`metadata.superseded_by=新id`；不物理删（好审计）。  
2. **检索后：** 同一主题多条都进 Top-K 时，按 `user_explicit` > 新 `updated_at` > `salience` 排序，可只留 1～2 条。  
3. **生成时：** 系统提示写明：与本轮用户新陈述冲突时 **以本轮为准**；记忆之间冲突以较新/explicit 为准。小流量可靠 LLM 仲裁；不要静默覆盖档案类字段。

用户说「我改名叫李」：抽新事实 + superseded 旧姓名记忆。

---

## 10. 和 RAG 一起用时的融合（避免重复）

同一次问答可能：

- LTM：用户偏好、历史结论  
- RAG：当前选中文件的 chunk  

融合顺序建议：短期窗口 → 长期 Top-K →（若本轮是问答）RAG hits。  
标签分开，不要把 LTM 当 RAG source 引用页码。

若 LTM 的 `rag_digest` 与本次 RAG 原文矛盾：**以本次检索到的文档为准**，并考虑把 digest 标过期。

---

## 11. 短期记忆持久化（登录还在）——和 LTM 配套

长期解决不了「昨天这个会话的近 5 轮」。需要另做：

- MySQL `agent_session_messages`（user_id, session_id, records JSON 或行存）  
- 登录后用 session_id 灌回 `SessionMemoryStore`  
- 滚动摘要也可落库一列 `session_summary`  

这是短期持久化，**仍不是**长期向量记忆。

---

## 12. 推荐实施顺序

1. `memory_milvus_service.py` + Collection `user_memories`（先 CRUD + 单测假 embedding）  
2. `MainAgent.arun` 开头 retrieve，prompt 加一节（可先手动 insert 几条验证）  
3. 终答后异步 extract + upsert（含相似去重）  
4. 过期扫描（可挂现有 `backend` 定时脚本，不必一上来就 Celery）  
5. 用户「记住」快捷入口  
6. 可选：RAG 入库后 digest；MySQL 短期落库  

---

## 13. 小流量（≤10 人）可以简化的点

- 不做复杂 salience 学习，explicit=1.0，对话抽取=0.5  
- 定时任务用 cron/脚本一天一次即可  
- 先不上独立记忆管理 UI  
- embedding 复用 RAG 同一套 DashScope 模型，维度必须一致  

---

**一句话：**  
长期记忆 = **新 Collection + 新 service 文件**，与 `milvus_service.py` 的文档库并列、共用连接；按 `user_id` 隔离；对话结束后抽取、提问时按需 Top-K；冲突用 superseded + 时间 + 生成侧说明。不要改现有 `document_vectors` 凑合用。
