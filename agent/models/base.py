"""Chat 模型协议与通用数据结构。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ChatMessage:
    """统一消息格式。"""

    role: str  # system / user / assistant / tool
    content: str
    name: Optional[str] = None  # tool 名等
    tool_call_id: Optional[str] = None
    # assistant 消息上的原生 tool_calls（OpenAI 形状，仅运行时拼 API 用）
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class ToolCallRequest:
    """模型请求调用工具（若走原生 function calling；ReAct 文本模式可不使用）。"""

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResult:
    """一次模型调用的规范化结果。"""

    content: str
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0  # 输入 token
    completion_tokens: int = 0  # 输出 token
    latency_ms: float = 0.0
    ttft_ms: Optional[float] = None  # 流式首包延迟；非流式为 None
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    raw: Any = None


class ChatModel(ABC):
    """所有 Provider 需实现的统一接口。"""

    provider: str = "unknown"
    model_id: str = "unknown"

    @abstractmethod
    def complete(
        self,
        messages: List[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        tools: Optional[Sequence[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> ModelResult:
        """同步补全。tools 为 OpenAI function 定义列表。"""
