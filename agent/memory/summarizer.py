"""对话摘要器：把滚出窗口的旧轮次压成短文本。"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Protocol

from agent.models.base import ChatMessage
from agent.models.router import ModelRole, ModelRouter

logger = logging.getLogger("agent.memory.summarizer")

_SUMMARIZE_SYSTEM = """你是会话摘要器。把「已有摘要」与「刚滚出窗口的旧对话骨架」合并成一份更短的中文摘要。
输入通常只有 User / Thought / Final Answer，不含工具原文。
保留：用户目标、已确认事实、未完成事项、关键数字/时间、终答中的结论。
不要编造；不要逐句复述。控制在 400 字以内。只输出摘要正文。"""


class Summarizer(Protocol):
    async def merge(self, previous_summary: str, newly_evicted: str) -> str:
        ...


class HeuristicSummarizer:
    """无 LLM 时的降级：截断拼接，保证测试与离线可用。"""

    def __init__(self, max_chars: int = 1200) -> None:
        self.max_chars = max_chars

    async def merge(self, previous_summary: str, newly_evicted: str) -> str:
        prev = (previous_summary or "").strip()
        chunk = (newly_evicted or "").strip()
        if not chunk:
            return prev
        if not prev:
            merged = chunk
        else:
            merged = prev + "\n---\n" + chunk
        if len(merged) <= self.max_chars:
            return merged
        return merged[: self.max_chars].rstrip() + "…"


class LlmSummarizer:
    """用 fast 模型做增量合并摘要。失败则回退启发式。"""

    def __init__(
        self,
        router: ModelRouter,
        *,
        fallback: Optional[HeuristicSummarizer] = None,
    ) -> None:
        self.router = router
        self.fallback = fallback or HeuristicSummarizer()

    async def merge(self, previous_summary: str, newly_evicted: str) -> str:
        newly_evicted = (newly_evicted or "").strip()
        if not newly_evicted:
            return (previous_summary or "").strip()
        user = (
            f"## 已有摘要\n{(previous_summary or '（无）').strip()}\n\n"
            f"## 刚滚出窗口的对话\n{newly_evicted[:6000]}"
        )
        try:
            model = self.router.get(ModelRole.FAST, route_reason="memory_summarize")
            result = await asyncio.to_thread(
                model.complete,
                [
                    ChatMessage(role="system", content=_SUMMARIZE_SYSTEM),
                    ChatMessage(role="user", content=user),
                ],
                temperature=0.1,
                max_tokens=512,
            )
            text = (result.content or "").strip()
            if text:
                return text
        except Exception:
            logger.exception("记忆摘要 LLM 失败，改用启发式")
        return await self.fallback.merge(previous_summary, newly_evicted)
