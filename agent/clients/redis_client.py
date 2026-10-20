"""Agent 侧 Redis 客户端（与 backend 共用 REDIS_* 环境变量）。

命名空间（与 RAG 隔离）
----------------------
- agent:mem:{sid}:*       短期工作记忆
- agent:pending:{sid}     needs_input 挂起状态
- agent:skills:{sid}      会话技能粘滞

不要写入 session:* / rag:qa:*。
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

logger = logging.getLogger("agent.clients.redis")

_lock = threading.Lock()
_client: Any = None


def get_redis_client():
    """懒加载 redis.Redis；decode_responses=True 便于存 JSON 字符串。"""
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        import redis

        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        password = os.getenv("REDIS_PASSWORD") or None
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        client.ping()
        _client = client
        logger.info("Agent Redis 已连接 %s:%s db=%s", host, port, db)
        return _client


def agent_memory_ttl() -> int:
    """短期记忆 TTL（秒），默认 24h；清会话会主动 DEL，不依赖过期。"""
    try:
        return max(300, int(os.getenv("AGENT_MEMORY_TTL", "86400")))
    except (TypeError, ValueError):
        return 86400


def use_redis_memory() -> bool:
    """
    AGENT_MEMORY_BACKEND=redis|memory
    默认 redis；设为 memory 可回退进程内（单机调试）。
    """
    return (os.getenv("AGENT_MEMORY_BACKEND") or "redis").strip().lower() != "memory"
