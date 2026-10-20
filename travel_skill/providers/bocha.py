"""博查 Web Search。"""

from __future__ import annotations

from typing import Any

from travel_skill.logging_utils import get_logger
from travel_skill.shared.config import BOCHA_API_BASE, BOCHA_API_KEY
from travel_skill.shared.http_client import http_post

logger = get_logger("travel_skill.bocha")
REQUEST_TIMEOUT = 15


class BochaClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or BOCHA_API_KEY
        self.base_url = (base_url or BOCHA_API_BASE).rstrip("/")
        if not self.api_key:
            raise RuntimeError("未配置 BOCHA_API_KEY")

    def web_search(
        self,
        query: str,
        *,
        freshness: str = "oneYear",
        count: int = 8,
        summary: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/v1/web-search"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"query": query, "summary": summary, "freshness": freshness, "count": count}
        wrapped = http_post(
            url,
            headers=headers,
            json=payload,
            purpose="culture.web_search",
            provider="bocha",
            timeout=REQUEST_TIMEOUT,
        )
        if not wrapped.get("ok"):
            return {"ok": False, "error": wrapped.get("error"), "query": query, "snippets": []}

        body = wrapped.get("data") or {}
        data = body.get("data") or {}
        pages = (data.get("webPages") or {}).get("value") or []
        snippets = [
            {
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "summary": item.get("summary", ""),
                "site": item.get("siteName", ""),
                "published": item.get("datePublished", ""),
            }
            for item in pages
        ]
        return {"ok": True, "error": None, "query": query, "snippets": snippets}
