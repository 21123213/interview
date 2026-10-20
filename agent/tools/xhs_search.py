"""通用小红书搜索：关键词搜索 + 自动拉前几条笔记正文（无旅游线路模板）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List

from agent.tools.base import BaseTool, ToolResult, ToolSpec
from agent.travel.config import XHS_SKILLS_ROOT


def _skills_ready() -> bool:
    root = Path(XHS_SKILLS_ROOT) if XHS_SKILLS_ROOT else Path()
    return root.is_dir() and (root / "scripts" / "cli.py").is_file()


def _detail_limit(default: int = 5) -> int:
    raw = (os.getenv("AGENT_XHS_SEARCH_DETAIL_LIMIT") or "").strip()
    if not raw:
        return default
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return default


def _feed_card(feed: dict[str, Any]) -> dict[str, Any]:
    note_card = feed.get("noteCard") if isinstance(feed.get("noteCard"), dict) else {}
    return {
        "id": str(feed.get("id") or "").strip(),
        "xsecToken": str(feed.get("xsecToken") or "").strip(),
        "title": str(
            note_card.get("displayTitle")
            or feed.get("displayTitle")
            or feed.get("title")
            or ""
        ).strip(),
    }


class XhsSearchTool(BaseTool):
    spec = ToolSpec(
        name="xhs_search",
        description=(
            "小红书关键词搜索：返回笔记列表，并自动拉取前几条笔记正文"
            "（title/desc/body；不超过 50 字的短篇会丢弃）。"
            "需本机 Chrome 已登录且启用 XHS Bridge。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "max_notes": {
                    "type": "integer",
                    "description": "自动拉取正文的笔记条数，默认 5，最大 10",
                    "default": 5,
                },
            },
            "required": ["keyword"],
        },
        exec_mode="io",
    )

    def run(self, keyword: str = "", max_notes: int = 0, **_: Any) -> ToolResult:
        from travel_skill.providers.xhs import (
            get_feed_detail,
            is_note_usable,
            note_text_content,
            search_feeds,
        )
        from travel_skill.shared.config import XHS_NOTE_MIN_CHARS

        kw = (keyword or "").strip()
        if not kw:
            return ToolResult(ok=False, content="keyword 不能为空")
        limit = int(max_notes) if max_notes else _detail_limit()
        limit = max(1, min(10, limit))
        try:
            data = search_feeds(kw)
            feeds_raw = list(data.get("feeds") or [])
            feeds = [_feed_card(f) for f in feeds_raw if isinstance(f, dict)]
            notes: list[dict[str, Any]] = []
            skipped_short = 0
            errors: list[str] = []
            # 多看一些 feed，凑满 limit 条合格长文
            for feed in feeds_raw[: max(limit * 3, limit)]:
                if len(notes) >= limit:
                    break
                if not isinstance(feed, dict):
                    continue
                fid = str(feed.get("id") or "").strip()
                token = str(feed.get("xsecToken") or "").strip()
                if not fid or not token:
                    continue
                try:
                    detail = get_feed_detail(fid, token, keyword=kw)
                    note = detail.get("note") or {}
                    body = str(note.get("body") or "")
                    desc = str(note.get("desc") or "")
                    packed = {
                        "feed_id": str(note.get("noteId") or fid),
                        "title": str(note.get("title") or ""),
                        "desc": desc,
                        "body": body,
                        "text": note_text_content({"body": body, "desc": desc}),
                    }
                    if not is_note_usable(packed, min_chars=XHS_NOTE_MIN_CHARS):
                        skipped_short += 1
                        continue
                    notes.append(packed)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{fid}: {exc}")
            payload = {
                "ok": True,
                "error": None,
                "keyword": kw,
                "feeds": feeds,
                "count": len(feeds),
                "notes": notes,
                "notes_count": len(notes),
                "skipped_short": skipped_short,
                "min_chars_exclusive": XHS_NOTE_MIN_CHARS,
                "detail_errors": errors,
            }
        except Exception as exc:  # noqa: BLE001
            payload = {
                "ok": False,
                "error": str(exc),
                "feeds": [],
                "count": 0,
                "notes": [],
                "notes_count": 0,
            }
        text = json.dumps(payload, ensure_ascii=False)
        return ToolResult(ok=bool(payload.get("ok")), content=text, data=payload)


XHS_GENERAL_TOOLS: List[BaseTool] = [XhsSearchTool()]


def register_xhs_general_tools(registry) -> None:
    if not _skills_ready():
        return
    for tool in XHS_GENERAL_TOOLS:
        registry.register(tool)
