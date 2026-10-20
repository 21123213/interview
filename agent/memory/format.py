"""把记忆记录格式化成可读文本（进 prompt 用）。"""

from __future__ import annotations

import json
from typing import List

from agent.memory.base import MemoryRecord

# 跨轮 / 摘要只保留这些角色；tool / action / observation 不进历史骨架
_SKELETON_ROLES = frozenset({"user", "thought", "assistant"})


def split_rounds(records: List[MemoryRecord]) -> List[List[MemoryRecord]]:
    """按 user 消息切轮：一轮 = 一次用户提问 + 其后直到下一问之前的过程。"""
    rounds: List[List[MemoryRecord]] = []
    current: List[MemoryRecord] = []
    for r in records:
        if r.role == "user" and current:
            rounds.append(current)
            current = [r]
        else:
            current.append(r)
    if current:
        rounds.append(current)
    return rounds


def format_skeleton_records(
    records: List[MemoryRecord],
    *,
    skip_leading_user: bool = False,
) -> str:
    """跨轮 / 摘要用骨架：User、Thought、Final Answer。不含 tool / action / observation。"""
    lines: List[str] = []
    skipped = False
    for r in records:
        if r.role not in _SKELETON_ROLES:
            continue
        if skip_leading_user and not skipped and r.role == "user":
            skipped = True
            continue
        text = (r.content or "").strip()
        if r.role == "user":
            lines.append(f"User: {r.content}")
        elif r.role == "thought":
            if text:
                lines.append(f"Thought: {r.content}")
        elif r.role == "assistant":
            kind = r.meta.get("kind") or ""
            if kind in ("plan", "review"):
                continue
            if not text:
                continue
            if kind == "final_answer":
                lines.append(f"Final Answer: {r.content}")
            else:
                # 调工具前的模型自述，当作思考过程
                lines.append(f"Thought: {r.content}")
    return "\n".join(lines)


def format_records(records: List[MemoryRecord], *, skip_leading_user: bool = False) -> str:
    """调试用全文渲染（含 tool）。进模型历史请用 format_skeleton_records。"""
    lines: List[str] = []
    skipped = False
    for r in records:
        if skip_leading_user and not skipped and r.role == "user":
            skipped = True
            continue
        if r.role == "user":
            lines.append(f"User: {r.content}")
        elif r.role == "thought":
            lines.append(f"Thought: {r.content}")
        elif r.role == "action":
            try:
                payload = json.loads(r.content)
                if "actions" in payload and isinstance(payload["actions"], list):
                    lines.append(
                        "Actions: " + json.dumps(payload["actions"], ensure_ascii=False)
                    )
                else:
                    lines.append(f"Action: {payload.get('action', '')}")
                    lines.append(
                        "Action Input: "
                        + json.dumps(payload.get("input") or {}, ensure_ascii=False)
                    )
            except json.JSONDecodeError:
                lines.append(f"Action: {r.content}")
        elif r.role == "tool":
            tname = r.meta.get("tool") or "tool"
            lines.append(f"Tool({tname}): {r.content}")
        elif r.role == "observation":
            # 已停止写入；旧会话若仍有记录则忽略，避免重复进 prompt
            continue
        elif r.role == "assistant":
            kind = r.meta.get("kind") or ""
            if kind in ("plan", "review"):
                continue
            if kind == "final_answer":
                lines.append(f"Final Answer: {r.content}")
            else:
                lines.append(f"Assistant: {r.content}")
        else:
            lines.append(f"[{r.role}] {r.content}")
    return "\n".join(lines)
