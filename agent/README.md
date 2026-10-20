# Agent

与 `backend`（RAG）平级的 Agent 运行时，**不使用 LangChain**。  
**ReAct** 使用 DashScope **原生 function calling**（tools API）；**Plan-Execute** 仍用文本 plan（见 `CHANGES_NATIVE_TOOLS.md`）。CLI 调试。

## 目录

```text
agent/
├── observability/   # TraceContext / Span / metrics / run_artifacts 落盘
├── resilience/      # 退避、熔断、sync+async 重试
├── models/          # ChatModel + DashScope + fast/strong
├── memory/          # 全量会话记忆
├── tools/           # ToolSpec.exec_mode + aexecute（local 线程池 / io 异步）
├── prompts/
├── runtime/         # ReAct / Plan-Execute
├── main_agent/      # MainAgent.arun / run
├── scripts/         # 观测日志清理等辅助脚本
├── logs/            # transcript / trace / metrics 文件输出
├── clients/
├── api/
├── cli.py
└── __main__.py
```

## 环境变量

```text
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_FAST_MODEL=qwen3.8-flash
DASHSCOPE_STRONG_MODEL=qwen3.8-max
# 或显式：AGENT_FAST_MODEL / AGENT_STRONG_MODEL（优先于 DASHSCOPE_*）
TRAVEL_MODEL_NAME=qwen3.8-max          # 旅游工具内 LLM（如需）
TRAVEL_MODEL_FALLBACK=qwen3.8-flash
XHS_NOTE_MIN_CHARS=50                  # 小红书正文须超过该字数才保留
AGENT_LOG_DIR=           # 可选；默认写到 agent/logs
```

## 终端调试

```bash
python -m agent
python -m agent --once "用 calculator 计算 (12+8)*3"
python -m agent --once "用 io_ping 探测一下" --show-transcript
python -m agent --no-save-artifacts   # 关闭三文件落盘
```

命令：`/memory` `/metrics` `/trace` `/clear` `/quit` `/pending`

## 怎么看 Trace / Metrics / Transcript

说明：下面这张表是**项目观测分层文档**（CLI → 小上线 → 以后），不是某次对话的原文记录。

| 阶段 | Trace | Metrics | Transcript |
|------|-------|---------|------------|
| 现在 CLI | 每轮写到 `agent/logs/trace/`；也可 `/trace` | 每轮写到 `agent/logs/metrics/`；也可 `/metrics` | 每轮写到 `agent/logs/transcript/`；也可 `--show-transcript` |
| 小上线 | 按日志 `trace_id` 串一次调用；可选返回 `trace_tree` | 进程内汇总，可再挂 Prometheus | 请求结果里的 `transcript` |
| 以后 | OTLP → Jaeger 等 | Grafana | 业务审计 / 回放 |

### 三文件落盘格式

每轮请求默认写出 **三个 JSON**（同一文件名，分目录）：

```text
agent/logs/
  transcript/YYYYMMDD/HHMMSS_<trace12>_<session12>.json
  trace/YYYYMMDD/HHMMSS_<trace12>_<session12>.json
  metrics/YYYYMMDD/HHMMSS_<trace12>_<session12>.json
```

统一外壳：

```json
{
  "schema": "agent.run_artifact.v1",
  "kind": "transcript | trace | metrics",
  "saved_at": "2026-10-08T12:00:00+08:00",
  "trace_id": "...",
  "session_id": "...",
  "mode": "react",
  "status": "ok",
  "steps": 2,
  "error": "",
  "payload": {}
}
```

- `transcript` 的 `payload`：逐步推理列表  
- `trace` 的 `payload`：Span 树（耗时、嵌套）  
- `metrics` 的 `payload`：进程内 counters / histograms 快照  

stderr 上的 INFO 日志仍是第三路（带 `trace=` / `session=`），与上述文件互补。

### 按保留期清理

三个脚本可直接启动；默认保留期不同，也可用 `--keep-days` 覆盖：

```bash
# transcript：默认保留 3 天
python -m agent.scripts.purge_transcript_logs
python -m agent.scripts.purge_transcript_logs --keep-days 3 --dry-run

# metrics：默认保留 7 天（一周）
python -m agent.scripts.purge_metrics_logs
python -m agent.scripts.purge_metrics_logs --list

# trace：默认保留 30 天（约一个月）
python -m agent.scripts.purge_trace_logs
python -m agent.scripts.purge_trace_logs --keep-days 30 --json
```

共用参数：`--keep-days` / `--dry-run` / `--list` / `--log-dir` / `--json`。

## 工具执行模式（不给模型填）

在 `ToolSpec.exec_mode`（不是 Action Input）：

- `local`：`asyncio.to_thread(run)` — calculator / get_time / echo
- `io`：`await arun` — io_ping（演示）；真实 HTTP 工具同此

## 本次改动清单（请对照阅读）

见下方「改动清单」；实现对应方案 B + 日志 + exec_mode + async 主路径。
