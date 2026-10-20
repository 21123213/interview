"""Agent 流式事件总线：单路 SSE 上按 event 类型分流到聊天 / 日志。

用法：
- API 层用 ``async for ev in agent.astream(...)`` 转成 SSE
- 运行中通过 ``emit_stream`` 或 logging Handler 推事件
- 不依赖 RAG / DB
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional

_stream_queue: ContextVar[Optional[asyncio.Queue]] = ContextVar(
    "agent_stream_queue", default=None
)

# 避免把超长日志灌进前端
_MAX_LOG_CHARS = 2000
_AGENT_LOG_PREFIXES = (
    "agent.",
    "travel_skill.",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StreamEvent:
    """一条可直接映射为 SSE 的事件。"""

    event: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        import json

        return (
            f"event: {self.event}\n"
            f"data: {json.dumps(self.data, ensure_ascii=False)}\n\n"
        )


def get_stream_queue() -> Optional[asyncio.Queue]:
    return _stream_queue.get()


def set_stream_queue(queue: Optional[asyncio.Queue]) -> Token:
    return _stream_queue.set(queue)


def reset_stream_queue(token: Token) -> None:
    _stream_queue.reset(token)


def emit_stream(event: str, **data: Any) -> None:
    """向当前请求的流队列推送事件（无队列时静默忽略）。"""
    queue = get_stream_queue()
    if queue is None:
        return
    payload = dict(data)
    payload.setdefault("ts", _utc_now_iso())
    try:
        queue.put_nowait(StreamEvent(event=event, data=payload))
    except Exception:  # noqa: BLE001
        pass


def emit_log(
    message: str,
    *,
    level: str = "INFO",
    source: str = "runtime",
    **extra: Any,
) -> None:
    text = (message or "").strip()
    if len(text) > _MAX_LOG_CHARS:
        text = text[: _MAX_LOG_CHARS - 3] + "..."
    emit_stream("log", level=level.upper(), source=source, message=text, **extra)


class StreamLogHandler(logging.Handler):
    """把 agent / travel_skill 日志桥到 SSE log 事件（右侧面板）。"""

    def emit(self, record: logging.LogRecord) -> None:
        if get_stream_queue() is None:
            return
        name = record.name or ""
        if not name.startswith(_AGENT_LOG_PREFIXES):
            return
        try:
            msg = self.format(record) if self.formatter else record.getMessage()
        except Exception:  # noqa: BLE001
            msg = record.getMessage()
        level = record.levelname or "INFO"
        source = "tool_llm" if "llm" in name.lower() else "runtime"
        if name.startswith("travel_skill"):
            source = "tool"
        emit_log(msg, level=level, source=source, logger=name)


_shared_handler: Optional[StreamLogHandler] = None
_shared_handler_lock = threading.Lock()


def ensure_stream_logging(level: int = logging.INFO) -> None:
    """进程内只挂一个 Handler；靠 ContextVar 把日志路由到当前请求队列。"""
    global _shared_handler
    with _shared_handler_lock:
        if _shared_handler is not None:
            return
        handler = StreamLogHandler(level=level)
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        _shared_handler = handler


def attach_stream_logging(level: int = logging.INFO) -> StreamLogHandler:
    """兼容旧调用：确保已安装共享 Handler，并返回它。"""
    ensure_stream_logging(level)
    assert _shared_handler is not None
    return _shared_handler


def detach_stream_logging(handler: Optional[StreamLogHandler] = None) -> None:
    """流式请求结束不卸载共享 Handler（避免并发互相摘掉）。"""
    del handler


async def drain_queue(queue: asyncio.Queue) -> AsyncIterator[StreamEvent]:
    while True:
        try:
            ev = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        yield ev


async def iter_with_task(
    queue: asyncio.Queue,
    task: "asyncio.Task[Any]",
    *,
    poll_timeout: float = 0.15,
) -> AsyncIterator[StreamEvent]:
    """边跑 task 边吐出队列事件；task 结束后排空队列。"""
    while not task.done():
        try:
            ev = await asyncio.wait_for(queue.get(), timeout=poll_timeout)
            yield ev
        except asyncio.TimeoutError:
            continue
    async for ev in drain_queue(queue):
        yield ev
    exc = task.exception() if not task.cancelled() else None
    if exc is not None:
        raise exc
