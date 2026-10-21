# RAG-FOR-BEGINNERS

面向初学者的 RAG + Agent 全栈项目：文档上传与解析、向量/BM25 混合检索、可选 Cross-Encoder 重排、流式问答，以及旅游等工具型 Agent。

> 快速启动与环境配置见 [QUICK_START.md](./QUICK_START.md)。Agent 细节见 [agent/README.md](./agent/README.md)。

## 功能概览

| 模块 | 说明 |
|------|------|
| **文档流水线** | 上传 → 解析/分块 → Embedding → 入 Milvus / MySQL |
| **RAG 问答** | 问句改写 → 扩写 → 向量 + BM25 → 多层 RRF → 可选 DashScope Rerank → LLM |
| **会话记忆** | Redis 上下文 + MySQL 落库；QA 缓存 |
| **Agent** | ReAct / Plan-Execute，旅游工具、搜索等（与 backend 平级） |
| **前端** | 登录注册、文件处理进度、RAG 聊天、Agent 页 |

## 项目结构

```
RAG-FOR-BEGINNERS/
├── backend/                            # FastAPI 后端（RAG 主服务）
│   ├── app/
│   │   ├── main.py                     # 应用入口
│   │   ├── database.py                 # 数据库连接
│   │   ├── api/                        # HTTP / WebSocket 路由
│   │   │   ├── auth.py                 # 登录注册 / 短信
│   │   │   ├── file.py                 # 文件上传与处理状态
│   │   │   ├── chat.py                 # RAG 问答（同步/流式）
│   │   │   ├── agent.py                # Agent HTTP 入口
│   │   │   └── websocket.py            # 文件处理进度推送
│   │   ├── core/                       # 检索与基础设施
│   │   │   ├── retrieval_pipeline.py   # 检索主流程（改写→扩写→双路→RRF→Rerank）
│   │   │   ├── query_understanding.py  # 问句改写 / 独立问句
│   │   │   ├── query_expand.py         # 查询扩写
│   │   │   ├── keyword_retrieval.py    # BM25 稀疏检索
│   │   │   ├── milvus_service.py       # 向量检索（Milvus）
│   │   │   ├── fusion.py               # 加权 RRF 融合
│   │   │   ├── reranker.py             # DashScope TextReRank 重排
│   │   │   ├── rag.py                  # Embedding / 答案生成
│   │   │   ├── qa_cache.py             # 问答缓存指纹
│   │   │   ├── session_memory.py       # 会话上下文
│   │   │   ├── rag_trace.py            # 分阶段可观测日志
│   │   │   ├── redis_manager.py        # Redis
│   │   │   ├── llm_utils.py            # DashScope Chat 封装
│   │   │   ├── agent_service.py        # 对接 agent 运行时
│   │   │   ├── security.py             # JWT 等安全
│   │   │   └── sms.py                  # 阿里云 PNVS 短信
│   │   ├── tasks/
│   │   │   └── file_processing.py      # 解析 / 分块 / Embedding 异步任务
│   │   ├── models/                     # ORM 模型
│   │   ├── schemas/                    # Pydantic 请求/响应
│   │   └── utils/
│   ├── scripts/                        # 评测、迁移、备份
│   │   ├── eval_rag.py                 # RAG 评测
│   │   ├── review_failures.py          # 失败样例复查
│   │   └── EVAL_README.md
│   ├── docs/
│   │   └── RAG_QA_PIPELINE.md          # 问答流水线说明
│   ├── migrations/                     # SQL 迁移
│   ├── uploads/                        # 上传文件落盘
│   ├── logs/                           # rag_trace.jsonl 等（gitignore）
│   └── requirements.txt
├── frontend/                           # React + Vite 前端
│   └── src/
│       ├── api/                        # auth / file / chat / agent
│       ├── pages/                      # Login / Register / Main / Agent
│       ├── components/                 # 上传进度等
│       ├── hooks/                      # WebSocket / 文件进度
│       └── utils/
├── agent/                              # Agent 运行时（与 backend 平级）
│   ├── main_agent/                     # MainAgent 入口
│   ├── runtime/                        # ReAct / Plan-Execute 循环
│   ├── models/                         # DashScope 等模型路由
│   ├── memory/                         # 会话记忆
│   ├── tools/                          # 内置工具 / 旅游 / 搜索
│   ├── travel/                         # 旅游相关客户端与执行
│   ├── skills/                         # Skill 定义（如 travel）
│   ├── observability/                  # Trace / metrics / 落盘
│   ├── resilience/                     # 重试 / 熔断 / 退避
│   ├── prompts/                        # Planner / ReAct 提示词
│   ├── clients/                        # Redis / 外部 MCP 等
│   ├── cli.py                          # 终端调试入口
│   └── README.md
├── travel_skill/                       # 旅游工具实现包（可被 agent 引用）
│   ├── tools/                          # weather / route / stay 等
│   ├── providers/                      # 和风 / 小红书等 Provider
│   ├── schemas/                        # 入参出参
│   └── shared/                         # HTTP / LLM / 配置
├── scripts/                            # 仓库级辅助脚本（探针、补丁等）
├── db/                                 # 本地向量/数据目录（gitignore）
├── .env                                # 本地密钥（勿提交）
├── .gitignore
├── QUICK_START.md                      # 环境与启动指南
└── README.md
```

## 技术栈（摘要）

- **后端**：FastAPI、MySQL、Redis、Milvus、DashScope（Embedding / Chat / TextReRank）
- **前端**：React、Vite、TypeScript
- **Agent**：自研 ReAct / Plan-Execute（非 LangChain），DashScope function calling

## License

MIT
