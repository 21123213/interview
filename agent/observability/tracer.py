"""轻量 Span 追踪器。

方案 B：活跃 span 栈按请求隔离（ContextVar），多用户并发互不串台。
进程内仍保留 last_root，供 CLI `/trace` 查看「最近一次」完成的树。
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

from agent.observability.context import get_trace_id

logger = logging.getLogger("agent.tracer")


@dataclass
class Span:
    """一次有起止时间的操作区间。"""

    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: Optional[str] = None
    trace_id: str = ""
    start_ms: float = field(default_factory=lambda: time.time() * 1000)
    end_ms: Optional[float] = None
    status: str = "ok"
    attrs: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    children: List["Span"] = field(default_factory=list)

    @property
    def latency_ms(self) -> float:
        end = self.end_ms if self.end_ms is not None else time.time() * 1000
        return max(0.0, end - self.start_ms)

    def add_event(self, name: str, **attrs: Any) -> None:
        """向 span 追加一条事件（观测用，不进 Agent 上下文）。"""
        self.events.append(
            {
                "name": name,
                "ts_ms": time.time() * 1000,
                "attrs": attrs,
            }
        )

    def end(self, status: str = "ok", **attrs: Any) -> None:
        self.end_ms = time.time() * 1000
        self.status = status
        if attrs:
            self.attrs.update(attrs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "trace_id": self.trace_id,
            "latency_ms": round(self.latency_ms, 2),
            "status": self.status,
            "attrs": self.attrs,
            "events": self.events,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class _SpanState:
    """单个请求绑定的 span 状态（存在 ContextVar 里）。"""

    stack: List[Span] = field(default_factory=list)
    root: Optional[Span] = None


# 每个 asyncio Task / 线程上下文各自一份，避免多用户抢同一栈
_span_state: ContextVar[Optional[_SpanState]] = ContextVar(
    "agent_span_state", default=None
)


class Tracer:
    """追踪器门面：逻辑单例，但栈数据按请求隔离。"""

    def __init__(self) -> None:
        # 最近一次「已结束」的根 span，给 CLI /trace 用（可被后一次请求覆盖）
        self._last_root: Optional[Span] = None

    def _state(self) -> _SpanState:
        state = _span_state.get()
        if state is None:
            state = _SpanState()
            _span_state.set(state)
        return state

    def reset(self) -> None:
        """当前请求开始时调用：换一份空的 span 状态。"""
        _span_state.set(_SpanState())

    @property
    def current(self) -> Optional[Span]:
        state = _span_state.get()
        if not state or not state.stack:
            return None
        return state.stack[-1]

    @property
    def root(self) -> Optional[Span]:
        """优先当前请求的树；请求已结束后回退到 last_root（CLI 调试）。"""
        state = _span_state.get()
        if state and state.root is not None:
            return state.root
        return self._last_root

    @contextmanager
    def span(
        self,
        name: str,
        *,
        parent: Optional[Span] = None,
        use_stack: bool = True,
        **attrs: Any,
    ) -> Generator[Span, None, None]:
        """创建子 span；异常时标记 status=error。

        parent: 显式指定父节点（并行工具调用时用，避免依赖栈顶）。
        use_stack: False 时不压入 ContextVar 栈，供 asyncio.gather 并行子 span，
                   否则多任务共享同一栈会把兄弟节点错误嵌套成父子链。
        """
        state = self._state()
        if parent is None:
            parent = state.stack[-1] if state.stack else None
        sp = Span(
            name=name,
            parent_span_id=parent.span_id if parent else None,
            trace_id=get_trace_id() or (parent.trace_id if parent else ""),
            attrs=dict(attrs),
        )
        if parent is None:
            state.root = sp
        else:
            parent.children.append(sp)
        if use_stack:
            state.stack.append(sp)
        logger.debug("span.start name=%s span_id=%s", name, sp.span_id)
        try:
            yield sp
            if sp.end_ms is None:
                sp.end(status="ok")
        except Exception as exc:  # noqa: BLE001
            sp.end(status="error", error_class=type(exc).__name__, error=str(exc))
            raise
        finally:
            if use_stack and state.stack and state.stack[-1] is sp:
                state.stack.pop()
            # 根 span 结束：留给 CLI 查看
            if parent is None:
                self._last_root = sp
            logger.debug(
                "span.end name=%s status=%s latency_ms=%.1f",
                name,
                sp.status,
                sp.latency_ms,
            )


_tracer = Tracer()


def get_tracer() -> Tracer:
    return _tracer
