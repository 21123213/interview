"""会话级技能粘滞：Redis 存 skill_ids 列表。

Key: agent:skills:{session_id}
与 memory / pending 同 TTL；clear 会话时一并删除。
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from agent.clients.redis_client import agent_memory_ttl, get_redis_client

logger = logging.getLogger("agent.runtime.skills_redis")


def _key(session_id: str) -> str:
    return f"agent:skills:{session_id}"


class RedisSessionSkillsStore:
    """session_id → skill_ids；替代 MainAgent._session_skills 进程 dict。"""

    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        self._ttl = ttl_seconds if ttl_seconds is not None else agent_memory_ttl()
        self._r = get_redis_client()

    def get(self, session_id: str) -> List[str]:
        raw = self._r.get(_key(session_id))
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data]
        except json.JSONDecodeError:
            logger.warning("skills 反序列化失败 session=%s", session_id)
        return []

    def set(self, session_id: str, skill_ids: List[str]) -> None:
        self._r.setex(
            _key(session_id),
            self._ttl,
            json.dumps(list(skill_ids), ensure_ascii=False),
        )

    def clear(self, session_id: str) -> None:
        self._r.delete(_key(session_id))

    def pop(self, session_id: str, default: Optional[List[str]] = None) -> List[str]:
        # 兼容 dict.pop 用法
        cur = self.get(session_id)
        self.clear(session_id)
        return cur if cur else (default or [])
