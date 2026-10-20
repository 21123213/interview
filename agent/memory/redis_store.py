"""基于 Redis 的会话工作记忆。

设计
----
- compact / format_for_prompt 仍在 SessionMemoryStore（应用层）执行：
  压缩逻辑（算溢出轮、调 summarizer）不进 Redis Lua，只把读写换成 Redis。
- 本类覆盖「记录列表 + summary + absorbed」的持久化；父类算法不变。
- clear(session_id) 删除该会话全部 agent:mem:{sid}:* key，
  与前端 DELETE /api/agent/session/{id} 对齐。

Key 布局
--------
agent:mem:{sid}:records   JSON 数组 MemoryRecord
agent:mem:{sid}:summary   滚动摘要字符串
agent:mem:{sid}:absorbed  已吸收轮数（int 字符串）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agent.clients.redis_client import agent_memory_ttl, get_redis_client
from agent.memory.base import MemoryRecord
from agent.memory.summarizer import Summarizer
from agent.memory.windowed import SessionMemoryStore

logger = logging.getLogger("agent.memory.redis")


def _records_key(session_id: str) -> str:
    return f"agent:mem:{session_id}:records"


def _summary_key(session_id: str) -> str:
    return f"agent:mem:{session_id}:summary"


def _absorbed_key(session_id: str) -> str:
    return f"agent:mem:{session_id}:absorbed"


def _record_to_dict(record: MemoryRecord) -> Dict[str, Any]:
    return {
        "role": record.role,
        "content": record.content,
        "timestamp": record.timestamp,
        "meta": record.meta or {},
    }


def _dict_to_record(item: Dict[str, Any]) -> MemoryRecord:
    return MemoryRecord(
        role=str(item.get("role") or "user"),
        content=str(item.get("content") or ""),
        timestamp=str(item.get("timestamp") or ""),
        meta=dict(item.get("meta") or {}),
    )


class RedisSessionMemoryStore(SessionMemoryStore):
    """SessionMemoryStore 的 Redis 后端：算法继承，存储换 Redis。"""

    def __init__(
        self,
        *,
        recent_rounds: int = 3,
        max_history_chars: int = 20000,
        summarizer: Optional[Summarizer] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        # 父类仍会建进程内 dict，但我们覆盖读写后不再依赖它们
        super().__init__(
            recent_rounds=recent_rounds,
            max_history_chars=max_history_chars,
            summarizer=summarizer,
        )
        self._ttl = ttl_seconds if ttl_seconds is not None else agent_memory_ttl()
        self._r = get_redis_client()

    def _touch(self, session_id: str) -> None:
        """刷新该会话相关 key 的 TTL。"""
        pipe = self._r.pipeline()
        for key in (
            _records_key(session_id),
            _summary_key(session_id),
            _absorbed_key(session_id),
        ):
            pipe.expire(key, self._ttl)
        pipe.execute()

    def append(self, session_id: str, record: MemoryRecord) -> None:
        key = _records_key(session_id)
        raw = self._r.get(key)
        items: List[Dict[str, Any]] = []
        if raw:
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                items = []
        items.append(_record_to_dict(record))
        self._r.setex(key, self._ttl, json.dumps(items, ensure_ascii=False))
        self._touch(session_id)

    def get_all(self, session_id: str) -> List[MemoryRecord]:
        raw = self._r.get(_records_key(session_id))
        if not raw:
            return []
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return [_dict_to_record(x) for x in items if isinstance(x, dict)]

    def clear(self, session_id: str) -> None:
        """清空该会话记忆（前端清除会话会调到这里）。"""
        self._r.delete(
            _records_key(session_id),
            _summary_key(session_id),
            _absorbed_key(session_id),
        )
        # 同步清掉父类残留（若曾混用）
        with self._lock:
            self._summary.pop(session_id, None)
            self._absorbed_rounds.pop(session_id, None)
        logger.info("已清空 Redis 记忆 session=%s", session_id)

    def get_summary(self, session_id: str) -> str:
        return self._r.get(_summary_key(session_id)) or ""

    def _set_summary(self, session_id: str, text: str) -> None:
        self._r.setex(_summary_key(session_id), self._ttl, text or "")
        self._touch(session_id)

    def _get_absorbed(self, session_id: str) -> int:
        raw = self._r.get(_absorbed_key(session_id))
        if raw is None:
            return 0
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def _set_absorbed(self, session_id: str, n: int) -> None:
        self._r.setex(_absorbed_key(session_id), self._ttl, str(int(n)))
        self._touch(session_id)
