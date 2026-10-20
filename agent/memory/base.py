"""记忆抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryRecord:
    """一条记忆记录（全量模式下尽量保留原始信息）。"""

    role: str  # user / assistant / system / thought / action / tool（observation 已停用）
    content: str
    timestamp: str = field(default_factory=_utc_now_iso)
    meta: Dict[str, Any] = field(default_factory=dict)


class MemoryStore(ABC):
    """会话记忆接口。"""

    @abstractmethod
    def append(self, session_id: str, record: MemoryRecord) -> None:
        ...

    @abstractmethod
    def get_all(self, session_id: str) -> List[MemoryRecord]:
        ...

    @abstractmethod
    def clear(self, session_id: str) -> None:
        ...

    def as_chat_transcript(self, session_id: str) -> str:
        """把全量记忆拼成可读文本，供拼进 prompt（调试期简单粗暴）。"""
        lines: List[str] = []
        for r in self.get_all(session_id):
            lines.append(f"[{r.role}] {r.content}")
        return "\n".join(lines)
