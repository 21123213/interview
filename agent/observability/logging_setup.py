"""结构化日志初始化：强制带上 trace_id / session_id，便于按次排查。"""

from __future__ import annotations

import logging
import sys

from agent.observability.context import get_trace_context


class TraceContextFilter(logging.Filter):
    """把当前请求的 TraceContext 写入 LogRecord，供 Formatter 使用。"""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_trace_context()
        record.trace_id = ctx.trace_id if ctx else "-"  # type: ignore[attr-defined]
        record.session_id = ctx.session_id if ctx else "-"  # type: ignore[attr-defined]
        record.user_id = (ctx.user_id if ctx and ctx.user_id else "-")  # type: ignore[attr-defined]
        return True


def setup_logging(level: str = "INFO") -> None:
    """配置根 logger。重复调用只更新级别，不叠加 handler。"""
    root = logging.getLogger()
    desired = getattr(logging, level.upper(), logging.INFO)

    if root.handlers:
        root.setLevel(desired)
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(TraceContextFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                "%(asctime)s [%(levelname)s] %(name)s "
                "trace=%(trace_id)s session=%(session_id)s: %(message)s"
            ),
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(desired)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
