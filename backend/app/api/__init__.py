"""API路由模块"""
from .auth import router as auth_router
from .file import router as file_router
from .chat import router as chat_router
from .agent import router as agent_router

__all__ = ["auth_router", "file_router", "chat_router", "agent_router"]
