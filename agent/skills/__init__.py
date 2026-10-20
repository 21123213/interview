"""Agent Skills：按用户意图注入 Markdown 技能说明。"""

from agent.skills.loader import (
    append_skills_for_ids,
    append_skills_if_needed,
    looks_like_travel,
    merge_session_skills,
    resolve_skills,
)

__all__ = [
    "append_skills_for_ids",
    "append_skills_if_needed",
    "looks_like_travel",
    "merge_session_skills",
    "resolve_skills",
]
