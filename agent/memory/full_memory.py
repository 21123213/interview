"""全量记忆：会话内所有步骤原样追加，不做截断 / 摘要。

后续若上下文过长，再换成滑动窗口或摘要记忆即可。
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Dict, List

from agent.memory.base import MemoryRecord, MemoryStore


class FullMemoryStore(MemoryStore):
    """进程内全量存储（按 session_id 分桶）。"""

    def __init__(self) -> None:
        self._data: Dict[str, List[MemoryRecord]] = defaultdict(list)
        self._lock = threading.Lock()

    def append(self, session_id: str, record: MemoryRecord) -> None:
        with self._lock:
            self._data[session_id].append(record)

    def get_all(self, session_id: str) -> List[MemoryRecord]:
        with self._lock:
            return list(self._data.get(session_id, []))

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._data.pop(session_id, None)

    def session_ids(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())
