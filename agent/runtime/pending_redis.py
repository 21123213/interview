"""PendingStore 的 Redis 实现：needs_input 跨进程可 resume。

Key: agent:pending:{session_id}
TTL 与 AGENT_MEMORY_TTL 一致；clear / pop 主动删除。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agent.clients.redis_client import agent_memory_ttl, get_redis_client
from agent.runtime.pending import AskQuestion, PendingState, PendingStore

logger = logging.getLogger("agent.runtime.pending_redis")


def _key(session_id: str) -> str:
    return f"agent:pending:{session_id}"


def _state_to_dict(state: PendingState) -> Dict[str, Any]:
    return {
        "mode": state.mode,
        "source": state.source,
        "user_input": state.user_input,
        "resume_token": state.resume_token,
        "payload": state.payload,
        "questions": [q.to_dict() for q in state.questions],
    }


def _dict_to_state(data: Dict[str, Any]) -> PendingState:
    questions: List[AskQuestion] = []
    for q in data.get("questions") or []:
        if not isinstance(q, dict):
            continue
        questions.append(
            AskQuestion(
                id=str(q.get("id") or ""),
                field=str(q.get("field") or ""),
                prompt=str(q.get("prompt") or ""),
                tool=str(q.get("tool") or ""),
                call_id=str(q.get("call_id") or ""),
            )
        )
    return PendingState(
        mode=str(data.get("mode") or ""),
        source=data.get("source") or "user_gap",  # type: ignore[arg-type]
        questions=questions,
        user_input=str(data.get("user_input") or ""),
        resume_token=str(data.get("resume_token") or ""),
        payload=dict(data.get("payload") or {}),
    )


class RedisPendingStore(PendingStore):
    """与内存 PendingStore 同接口，数据落 Redis。"""

    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        # 不调用父类 _items；保留锁语义用不到
        super().__init__()
        self._ttl = ttl_seconds if ttl_seconds is not None else agent_memory_ttl()
        self._r = get_redis_client()

    def put(self, session_id: str, state: PendingState) -> None:
        self._r.setex(
            _key(session_id),
            self._ttl,
            json.dumps(_state_to_dict(state), ensure_ascii=False),
        )

    def get(self, session_id: str) -> Optional[PendingState]:
        raw = self._r.get(_key(session_id))
        if not raw:
            return None
        try:
            return _dict_to_state(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("pending 反序列化失败 session=%s: %s", session_id, e)
            return None

    def pop(self, session_id: str) -> Optional[PendingState]:
        state = self.get(session_id)
        self._r.delete(_key(session_id))
        return state

    def clear(self, session_id: str) -> None:
        self._r.delete(_key(session_id))
