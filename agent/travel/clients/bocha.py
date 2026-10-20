"""博查 Web Search。"""

from __future__ import annotations

from typing import Any

from agent.travel.config import BOCHA_API_BASE, BOCHA_API_KEY
from agent.travel.http import http_post


class BochaClient:
    def web_search(
        self,
        query: str,
        *,
        freshness: str = "oneYear",
        count: int = 8,
    ) -> dict[str, Any]:
        if not BOCHA_API_KEY:
            return {"ok": False, "error": "未配置 BOCHA_API_KEY", "snippets": []}
        url = f"{BOCHA_API_BASE.rstrip('/')}/v1/web-search"
        wrapped = http_post(
            url,
            headers={
                "Authorization": f"Bearer {BOCHA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "summary": True,
                "freshness": freshness,
                "count": count,
            },
            timeout=15,
        )
        if not wrapped.get("ok"):
            return {"ok": False, "error": wrapped.get("error"), "snippets": []}
        body = wrapped.get("data") or {}
        data = body.get("data") or {}
        pages = (data.get("webPages") or {}).get("value") or []
        snippets = [
            {
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "summary": item.get("summary", ""),
            }
            for item in pages
        ]
        return {"ok": True, "snippets": snippets}
