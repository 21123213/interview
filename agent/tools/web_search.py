"""通用博查搜索：无旅游上下文限制，query 原样检索。

P1 成本管控：默认少条数 + 单条摘要截断，避免把长网页原文灌进 ReAct 上下文。
完整原始结果不进模型；截断后的精简 JSON 才作为 tool message。
"""

from __future__ import annotations

import json
import os
from typing import Any, List

from agent.tools.base import BaseTool, ToolResult, ToolSpec
from agent.travel.clients.bocha import BochaClient


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# 单次搜索默认条数（原 8 → 5）；可用 AGENT_WEB_SEARCH_DEFAULT_COUNT 覆盖
_DEFAULT_COUNT = _env_int("AGENT_WEB_SEARCH_DEFAULT_COUNT", 5)
# 返回给模型的最多条数硬顶
_SNIPPET_CAP = _env_int("AGENT_WEB_SEARCH_SNIPPET_MAX", 5)
# 单条 summary 最大字符（中文约 2 字≈1 token）
_SUMMARY_CHARS = _env_int("AGENT_WEB_SEARCH_SUMMARY_CHARS", 500)


def _compact_snippets(data: dict[str, Any]) -> dict[str, Any]:
    """把博查结果压成短摘要列表，抑制上下文膨胀。

    保留 title/url/summary（截断）/site/published；丢掉过长正文与重复 URL。
    """
    raw = list(data.get("snippets") or [])
    seen_urls: set[str] = set()
    compact: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        summary = str(item.get("summary") or "").strip()
        if len(summary) > _SUMMARY_CHARS:
            summary = summary[:_SUMMARY_CHARS] + "…"
        compact.append(
            {
                "title": str(item.get("title") or "").strip(),
                "url": url,
                "summary": summary,
                "site": str(item.get("site") or "").strip(),
                "published": str(item.get("published") or "").strip(),
            }
        )
        if len(compact) >= _SNIPPET_CAP:
            break
    out = dict(data)
    out["snippets"] = compact
    # 标记已截断，便于 transcript / 排障识别
    out["truncated"] = True
    out["snippet_cap"] = _SNIPPET_CAP
    out["summary_chars"] = _SUMMARY_CHARS
    return out


class WebSearchTool(BaseTool):
    spec = ToolSpec(
        name="web_search",
        description=(
            "通用网页搜索（博查）。把要查的问题原样作为 query；"
            "不绑定旅游行程，适合任意资料检索。"
            "返回已截断的短摘要，请一次搜准、够用即停。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索问题或关键词"},
                "freshness": {
                    "type": "string",
                    "description": "时效：oneDay/oneWeek/oneMonth/oneYear/noLimit",
                    "default": "oneYear",
                },
                "count": {
                    "type": "integer",
                    "description": f"返回条数，默认 {_DEFAULT_COUNT}（服务端会再截断）",
                    "default": _DEFAULT_COUNT,
                },
            },
            "required": ["query"],
        },
        exec_mode="io",
    )

    def run(
        self,
        query: str = "",
        freshness: str = "oneYear",
        count: int = 0,
        **_: Any,
    ) -> ToolResult:
        q = (query or "").strip()
        if not q:
            return ToolResult(ok=False, content="query 不能为空")
        try:
            # 请求上游时也不超过 snippet 上限，少拉无效内容
            default_n = _DEFAULT_COUNT if not count else int(count)
            n = max(1, min(default_n, _SNIPPET_CAP, 20))
        except (TypeError, ValueError):
            n = min(_DEFAULT_COUNT, _SNIPPET_CAP)
        data = BochaClient().web_search(q, freshness=freshness or "oneYear", count=n)
        # P1：进模型的 content 必须是截断后的精简版
        compact = _compact_snippets(data if isinstance(data, dict) else {"ok": False, "snippets": []})
        text = json.dumps(compact, ensure_ascii=False)
        return ToolResult(ok=bool(compact.get("ok")), content=text, data=compact)


def register_web_search_tools(registry) -> None:
    registry.register(WebSearchTool())


WEB_SEARCH_TOOLS: List[BaseTool] = [WebSearchTool()]
