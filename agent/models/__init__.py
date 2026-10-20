"""多模型统一抽象与路由（非 LangChain）。"""

from agent.models.base import (
    ChatMessage,
    ChatModel,
    ModelResult,
    ToolCallRequest,
)
from agent.models.router import ModelRouter, ModelRole, get_default_router

__all__ = [
    "ChatMessage",
    "ChatModel",
    "ModelResult",
    "ToolCallRequest",
    "ModelRouter",
    "ModelRole",
    "get_default_router",
]
