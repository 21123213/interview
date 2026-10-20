"""会话工作记忆（短期）：全量记录 + 进 prompt 时窗口 + 增量摘要。

策略：
- 最近 recent_rounds 轮（默认 3）只以「对话骨架」进入 prompt
  （User / Thought / Final Answer；不含历史 tool 原文）
- 更早的轮次滚出窗口时，用「旧摘要 + 新滚出轮的骨架」增量合并
- 另有 max_history_chars：骨架文本过长时继续吸收最旧轮
- 压缩时机：每次用户新提问写入后 compact 一次（不是每个 ReAct step）

存储后端：
- 默认可由 RedisSessionMemoryStore 覆盖 append/get_all/clear/_set_summary 等；
- compact / format_for_prompt 始终在本类（应用层）执行，不把压缩逻辑下沉到 Redis。
- 进程内 FullMemoryStore 仍作默认实现（AGENT_MEMORY_BACKEND=memory）。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from agent.memory.format import format_skeleton_records, split_rounds
from agent.memory.full_memory import FullMemoryStore
from agent.memory.summarizer import HeuristicSummarizer, Summarizer

logger = logging.getLogger("agent.memory.window")


class SessionMemoryStore(FullMemoryStore):
    """短期工作记忆：全量存储 + 按窗口压缩后的 prompt 视图（骨架）。"""

    def __init__(
        self,
        *,
        recent_rounds: int = 3,
        max_history_chars: int = 20000,
        summarizer: Optional[Summarizer] = None,
    ) -> None:
        super().__init__()
        self.recent_rounds = max(1, recent_rounds)
        # 近窗骨架字符上限（中文约 2 字≈1 token，16000≈8k tokens 量级）
        self.max_history_chars = max(2000, max_history_chars)
        self.summarizer: Summarizer = summarizer or HeuristicSummarizer()
        # session_id → 滚动摘要（进程内；Redis 子类覆盖读写）
        self._summary: Dict[str, str] = {}
        # 已吸收进摘要的「已完成轮」数量（从最旧开始计）
        self._absorbed_rounds: Dict[str, int] = {}

    def clear(self, session_id: str) -> None:
        super().clear(session_id)
        with self._lock:
            self._summary.pop(session_id, None)
            self._absorbed_rounds.pop(session_id, None)

    def get_summary(self, session_id: str) -> str:
        with self._lock:
            return self._summary.get(session_id, "")

    def _set_summary(self, session_id: str, text: str) -> None:
        """写入滚动摘要；Redis 子类覆盖此方法即可，compact 无需改。"""
        with self._lock:
            self._summary[session_id] = text

    def _get_absorbed(self, session_id: str) -> int:
        with self._lock:
            return self._absorbed_rounds.get(session_id, 0)

    def _set_absorbed(self, session_id: str, n: int) -> None:
        with self._lock:
            self._absorbed_rounds[session_id] = int(n)

    def _completed_and_current(self, session_id: str):
        records = self.get_all(session_id)
        rounds = split_rounds(records)
        if not rounds:
            return [], []
        # 最后一轮 = 本轮进行中（含当前问题 + 已产生的过程）
        return rounds[:-1], rounds[-1]

    def _recent_keep_count(self, completed: List[List]) -> int:
        """轮数窗口与字符预算取更严者，至少保留 1 轮（若有）。"""
        if not completed:
            return 0
        keep = min(self.recent_rounds, len(completed))
        while keep > 1:
            recent = completed[-keep:]
            text = "\n\n".join(
                format_skeleton_records(rnd) for rnd in recent if rnd
            )
            if len(text) <= self.max_history_chars:
                break
            keep -= 1
        return keep

    async def compact(self, session_id: str) -> None:
        """若已完成轮超过窗口（或骨架超字符预算），把多出来的最旧轮增量并入摘要。

        只在「新用户消息写入之后」调用一次，避免每个工具步都打 LLM。
        摘要输入为对话骨架，不含 tool 原文。
        存储通过 get_summary / _set_summary / _get_absorbed / _set_absorbed，
        因此换 Redis 后端时本方法不用改。
        """
        completed, _current = self._completed_and_current(session_id)
        if not completed:
            return
        keep = self._recent_keep_count(completed)
        overflow = len(completed) - keep
        if overflow <= 0:
            return
        absorbed = self._get_absorbed(session_id)
        if overflow <= absorbed:
            return
        newly = completed[absorbed:overflow]
        text = "\n\n".join(
            format_skeleton_records(rnd) for rnd in newly if rnd
        )
        if not text.strip():
            self._set_absorbed(session_id, overflow)
            return
        prev = self.get_summary(session_id)
        logger.info(
            "压缩短期记忆 session=%s 新吸收轮=%s absorbed %s→%s",
            session_id,
            len(newly),
            absorbed,
            overflow,
        )
        merged = await self.summarizer.merge(prev, text)
        self._set_summary(session_id, merged)
        self._set_absorbed(session_id, overflow)

    def format_for_prompt(
        self,
        session_id: str,
        *,
        exclude_last_user: bool = True,
    ) -> str:
        """拼进模型的短期记忆：旧摘要 + 近 N 轮骨架 + 本轮已有骨架过程。"""
        completed, current = self._completed_and_current(session_id)
        summary = self.get_summary(session_id).strip()
        keep = self._recent_keep_count(completed) if completed else 0
        recent = completed[-keep:] if keep else []
        parts: List[str] = []
        if summary:
            parts.append("## 更早对话摘要\n" + summary)
        recent_text = "\n\n".join(
            format_skeleton_records(rnd) for rnd in recent if rnd
        )
        current_text = format_skeleton_records(
            current, skip_leading_user=exclude_last_user
        )
        body = "\n\n".join(x for x in (recent_text, current_text) if x.strip())
        if body:
            parts.append(
                f"## 最近最多 {self.recent_rounds} 轮对话骨架\n" + body
            )
        return "\n\n".join(parts)
