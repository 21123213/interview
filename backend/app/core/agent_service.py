"""Agent 单例适配：进程内共享 MainAgent，与 RAG / DB 无交集。

默认 memory/pending/skills 落 Redis（见 AGENT_MEMORY_BACKEND），
因此多 worker 也可共享同一会话状态；清除会话走 MainAgent.clear_session_state。
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_agent = None


def get_main_agent():
    """懒加载 MainAgent（跨请求共享；状态默认在 Redis）。"""
    global _agent
    if _agent is not None:
        return _agent
    with _lock:
        if _agent is not None:
            return _agent
        from agent.main_agent import MainAgent

        _agent = MainAgent()
        logger.info("MainAgent 已初始化 mode=%s", _agent.mode)
        return _agent


def reset_main_agent_for_tests() -> None:
    """测试用：清空单例。"""
    global _agent
    with _lock:
        _agent = None
