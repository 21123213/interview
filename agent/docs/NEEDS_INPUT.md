# 缺参暂停（needs_input）

## 两个概念

| 概念 | 是什么 | 在哪看 |
|------|--------|--------|
| **transcript** | 本轮推理步骤列表（plan / tool / needs_input 等） | `AgentRunResult.transcript`、CLI `--show-transcript` |
| **trace** | Span 树（耗时、嵌套调用、事件） | `AgentRunResult.trace_tree`、CLI `/trace` |
| **日志** | logger INFO 行 | 控制台 / 日志文件 |

三者互补：`needs_input` 会同时写入 transcript、当前请求的 trace span、以及 `needs_input ...` 日志。**trace 不是 transcript**，但都能看到缺参事件。

## 中断是否异步

- 运行时 **立刻返回** `status=needs_input`，不在事件循环里 `input()` 死等。
- Pending 按 `session_id` 存进程内；其它会话可照常 `arun`。
- CLI / 将来 API 在外壳收集答案后调用 `MainAgent.resume` / `aresume`。

## API 形态（约定）

请求跑完若缺参：

```json
{
  "status": "needs_input",
  "answer": "还需要确认：…",
  "pending": {
    "source": "user_gap",
    "resume_token": "...",
    "questions": [{"id":"q1","field":"start_date","prompt":"…"}]
  }
}
```

继续：`POST` 同一 `session_id` + `resume_token` + 用户答案（文本或 map）。
