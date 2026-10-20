"""观测层：上下文、结构化事件、Span 追踪、进程内指标。

说明：
- 重试次数、退避、熔断等只写到日志 / span / metrics，供排障与看板使用。
- 不把这些细节回传给主 Agent 的推理上下文（Observation 里不带 attempt）。
"""

from agent.observability.context import (
    TraceContext,
    clear_trace_context,
    get_trace_context,
    get_trace_id,
    new_trace_id,
    set_trace_context,
)
from agent.observability.metrics import MetricsRegistry, get_metrics
from agent.observability.tracer import Span, Tracer, get_tracer

__all__ = [
    "TraceContext",
    "clear_trace_context",
    "get_trace_context",
    "get_trace_id",
    "new_trace_id",
    "set_trace_context",
    "MetricsRegistry",
    "get_metrics",
    "Span",
    "Tracer",
    "get_tracer",
]
