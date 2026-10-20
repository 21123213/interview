"""结构化事件定义。

事件只用于观测（日志 / span / 指标），不进入 Agent Observation。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BaseEvent:
    """所有观测事件的公共字段。"""

    name: str
    trace_id: str = ""
    span_id: str = ""
    timestamp: str = field(default_factory=_utc_now_iso)
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LlmCallEvent(BaseEvent):
    """一次 LLM 调用结束后的汇总事件（不含「让 Agent 看」的重试叙事）。"""

    name: str = "llm.call"
    model: str = ""
    provider: str = ""
    role: str = ""  # 逻辑角色：fast / strong 等
    route_reason: str = ""
    prompt_tokens: int = 0  # 输入侧 token
    completion_tokens: int = 0  # 输出侧 token
    latency_ms: float = 0.0  # 端到端耗时
    ttft_ms: Optional[float] = None  # 首 token 延迟（非流式可为 None）
    status: str = "ok"  # ok / error
    error_class: str = ""


@dataclass
class ToolCallEvent(BaseEvent):
    """一次工具调用的最终结果事件（最终成功/失败，不强调中间 attempt）。"""

    name: str = "tool.call"
    tool_name: str = ""
    latency_ms: float = 0.0
    status: str = "ok"
    error_class: str = ""
    # 下列字段仅写观测层；不会塞进 Observation 给模型看
    attempt_count: int = 1
    circuit_state: str = ""


@dataclass
class NeedsInputEvent(BaseEvent):
    """缺参暂停（观测用）。同时会出现在 transcript 与当前请求的 trace span。"""

    name: str = "needs_input"
    source: str = ""  # user_gap / upstream_gap / tool_error
    tool: str = ""
    fields: str = ""
    mode: str = ""


@dataclass
class ResilienceEvent(BaseEvent):
    """韧性层内部事件：退避、熔断开闭、某次 attempt 失败等。

    仅打日志/指标，不暴露给主 Agent 推理。
    """

    name: str = "resilience"
    dependency: str = ""  # 如 tool:calculator / model:dashscope:qwen-turbo
    kind: str = ""  # attempt / backoff / circuit_open / circuit_close / ...
    attempt: int = 0
    backoff_ms: float = 0.0
    status: str = ""
    error_class: str = ""
