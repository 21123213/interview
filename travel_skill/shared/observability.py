"""travel_skill 观测：内存统计 + JSONL（LLM / tool 成本）。

写盘路径由环境变量 OBS_METRICS_JSONL 控制（默认 agent/logs/travel_skill/metrics.jsonl）。
每行 JSON 关键字段：
  - kind: "llm" | "tool" | "http" …
  - purpose: 业务名，如 get_weather / invoke 的 purpose
  - tokens_in / tokens_out: LLM 才有意义；tool 一般为 0
  - latency_ms / status / session_id
"""

from __future__ import annotations

import functools
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from travel_skill.logging_utils import get_logger
from travel_skill.shared.config import (
    LANGSMITH_TRACING,
    OBS_METRICS_JSONL,
    OBS_PRINT_SUMMARY,
    PROJECT_ROOT,
)

F = TypeVar("F", bound=Callable[..., Any])

logger = get_logger("travel_skill.obs")

_lock = threading.Lock()
_session_id: str = ""
_events: list[dict[str, Any]] = []


@dataclass
class CallStats:
    count: int = 0
    success: int = 0
    fallback: int = 0
    error: int = 0
    latency_ms_sum: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    retries: int = 0

    def record(
        self,
        *,
        status: str,
        latency_ms: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        retries: int = 0,
    ) -> None:
        self.count += 1
        self.latency_ms_sum += latency_ms
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.retries += retries
        if status == "success":
            self.success += 1
        elif status == "fallback":
            self.fallback += 1
        else:
            self.error += 1

    @property
    def avg_latency_ms(self) -> float:
        return self.latency_ms_sum / self.count if self.count else 0.0


_stats: dict[str, CallStats] = {}


def configure_langsmith() -> None:
    if not LANGSMITH_TRACING:
        return
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    if os.getenv("LANGCHAIN_API_KEY") and not os.getenv("LANGSMITH_API_KEY"):
        os.environ["LANGSMITH_API_KEY"] = os.environ["LANGCHAIN_API_KEY"]
    project = os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT") or "travel-skill"
    os.environ.setdefault("LANGCHAIN_PROJECT", project)
    logger.info("LangSmith tracing enabled project=%s", project)


def start_session(session_id: str | None = None) -> str:
    global _session_id, _events, _stats
    with _lock:
        _session_id = session_id or uuid.uuid4().hex[:12]
        _events = []
        _stats = {}
    configure_langsmith()
    logger.info("obs session start session_id=%s", _session_id)
    return _session_id


def get_session_id() -> str:
    return _session_id or "no-session"


def _append_event(event: dict[str, Any]) -> None:
    with _lock:
        _events.append(event)
        purpose = str(event.get("purpose") or "unknown")
        st = _stats.setdefault(purpose, CallStats())
        st.record(
            status=str(event.get("status") or "error"),
            latency_ms=float(event.get("latency_ms") or 0),
            tokens_in=int(event.get("tokens_in") or 0),
            tokens_out=int(event.get("tokens_out") or 0),
            retries=int(event.get("retries") or 0),
        )

    if OBS_METRICS_JSONL:
        path = Path(OBS_METRICS_JSONL)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def record_call(
    *,
    kind: str,
    purpose: str,
    status: str,
    latency_ms: float,
    provider: str = "",
    model: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
    retries: int = 0,
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    event: dict[str, Any] = {
        "ts": time.time(),
        "session_id": get_session_id(),
        "kind": kind,
        "purpose": purpose,
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "provider": provider,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "retries": retries,
        "error": (error or "")[:300],
    }
    if extra:
        event["extra"] = extra
    _append_event(event)
    level = logger.warning if status == "error" else logger.info
    level(
        "obs %s purpose=%s status=%s latency_ms=%.0f retries=%d tokens=%d/%d %s",
        kind,
        purpose,
        status,
        latency_ms,
        retries,
        tokens_in,
        tokens_out,
        f"err={error[:80]}" if error else "",
    )


def traced_tool(purpose: str) -> Callable[[F], F]:
    """装饰 travel_skill 工具实现：写入 kind=tool 的 obs 事件（算延迟/成败）。

    用法（注意写在 @tool 下面，保证 StructuredTool 调到的是本包装）：
        @tool(args_schema=...)
        @traced_tool("get_weather")
        def get_weather(...):
            ...
    tool 无 LLM token；成本看 latency_ms + 调用次数。LLM 成本看 kind=llm。
    """

    def deco(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            status = "success"
            err = ""
            try:
                result = fn(*args, **kwargs)
                # 业务失败多返回 ok=false，不抛异常
                if isinstance(result, dict) and result.get("ok") is False:
                    status = "error"
                    err = str(result.get("error") or result.get("code") or "")[:300]
                return result
            except Exception as exc:  # noqa: BLE001
                status = "error"
                err = str(exc)[:300]
                raise
            finally:
                record_call(
                    kind="tool",
                    purpose=purpose,
                    status=status,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    provider="travel_skill",
                    error=err,
                )

        return wrapper  # type: ignore[return-value]

    return deco


def get_stats_snapshot() -> dict[str, dict[str, Any]]:
    with _lock:
        return {
            k: {
                "count": v.count,
                "success": v.success,
                "fallback": v.fallback,
                "error": v.error,
                "avg_latency_ms": round(v.avg_latency_ms, 1),
                "tokens_in": v.tokens_in,
                "tokens_out": v.tokens_out,
                "retries": v.retries,
            }
            for k, v in sorted(_stats.items())
        }


def print_session_summary() -> None:
    if not OBS_PRINT_SUMMARY:
        return
    snap = get_stats_snapshot()
    if not snap:
        return
    print("\n===== obs summary (session=%s) =====" % get_session_id())
    for purpose, s in snap.items():
        print(
            f"{purpose}: n={s['count']} ok={s['success']} err={s['error']} "
            f"avg_ms={s['avg_latency_ms']} tokens={s['tokens_in']}/{s['tokens_out']}"
        )
