"""请求级追踪上下文（基于 contextvars，异步/多协程安全）。"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# 当前协程/任务绑定的追踪上下文
_trace_ctx: ContextVar[Optional["TraceContext"]] = ContextVar(
    "agent_trace_ctx", default=None
)


@dataclass
class TraceContext:
    """一次用户请求的根上下文。

    Attributes:
        trace_id: 整次调用的唯一 ID，串联所有 span / 日志。
        session_id: 会话 ID（可与记忆绑定）。
        user_id: 可选用户标识。
        agent_name: 主 Agent 名称。
        attrs: 可扩展的额外属性。
    """

    trace_id: str
    session_id: str = ""
    user_id: str = ""
    agent_name: str = "main_agent"
    attrs: Dict[str, Any] = field(default_factory=dict)


def new_trace_id() -> str:
    """生成新的 trace_id。"""
    return uuid.uuid4().hex


def get_trace_context() -> Optional[TraceContext]:
    """获取当前绑定的 TraceContext；未设置时返回 None。"""
    return _trace_ctx.get()


def get_trace_id() -> str:
    """便捷读取 trace_id；无上下文时返回空字符串。"""
    ctx = get_trace_context()
    return ctx.trace_id if ctx else ""


def set_trace_context(ctx: TraceContext) -> Token:
    """绑定追踪上下文，返回 Token 供 clear 时还原。"""
    return _trace_ctx.set(ctx)


def clear_trace_context(token: Optional[Token] = None) -> None:
    """清除或还原追踪上下文。"""
    if token is not None:
        _trace_ctx.reset(token)
    else:
        _trace_ctx.set(None)
