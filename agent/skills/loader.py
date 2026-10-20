"""按用户意图加载 Agent Skill（Markdown）到 system prompt。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

SKILLS_ROOT = Path(__file__).resolve().parent

# 旅游意图：含跟进改动线常用词（动线/博物馆/第N天），避免 follow-up 丢 skill
_TRAVEL_PATTERNS = re.compile(
    r"(旅游|旅行|出行|行程|攻略|玩法|景点|酒店|民宿|机票|高铁|"
    r"几日游|日游|天游|自由行|度假|周末去|打卡|闭馆|节假日|"
    r"规划.+游|去.+玩|游玩|出行计划|"
    # 跟进改行程：不说「旅游」也会命中
    r"动线|博物馆|博物院|安排一下|第[一二三四五六七八九十\d]+天|"
    r"weather|itinerary|hotel|trip|travel)",
    re.IGNORECASE,
)


def looks_like_travel(user_input: str) -> bool:
    text = (user_input or "").strip()
    if not text:
        return False
    return bool(_TRAVEL_PATTERNS.search(text))


def resolve_skills(user_input: str) -> list[str]:
    """根据用户输入解析应启用的 skill id 列表（可扩展）。"""
    skills: list[str] = []
    if looks_like_travel(user_input):
        skills.append("travel")
    return skills


def merge_session_skills(
    previous: Sequence[str],
    current: Sequence[str],
) -> list[str]:
    """会话级技能粘滞：本轮命中 ∪ 历史已启用，保序去重。

    例：第一轮开启 travel 后，用户说「第四天改去博物馆」即使正则漏网，
    仍保留 travel，避免降级成裸 web_search。
    """
    merged: list[str] = []
    for sid in list(previous) + list(current):
        s = str(sid or "").strip()
        if s and s not in merged:
            merged.append(s)
    return merged


def load_skill_markdown(relative: str) -> str:
    path = SKILLS_ROOT / relative
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    # 去掉 YAML front matter，只保留正文给模型
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()
    return text


def append_skills_for_ids(base_prompt: str, skill_ids: Sequence[str]) -> str:
    """按已解析/粘滞的 skill_ids 注入 SKILL.md（不依赖本轮原文正则）。"""
    chunks = [base_prompt.rstrip()]
    ids = {str(s).strip() for s in skill_ids if str(s).strip()}
    if "travel" in ids:
        body = load_skill_markdown("travel/SKILL.md")
        if body:
            chunks.append("## 已启用技能：旅游规划\n\n" + body)
    return "\n\n".join(chunks) + "\n"


def append_skills_if_needed(base_prompt: str, user_input: str) -> str:
    """兼容旧调用：仅按当前句解析 skill。新路径请用 append_skills_for_ids。"""
    return append_skills_for_ids(base_prompt, resolve_skills(user_input))
