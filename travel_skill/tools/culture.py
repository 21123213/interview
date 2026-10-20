"""get_culture：检索目的地闭馆与当地活动原始信息，由主 Agent LLM 判断是否贴合行程时间。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from travel_skill.errors import ToolError
from travel_skill.logging_utils import get_logger
from travel_skill.providers.bocha import BochaClient
from travel_skill.schemas.culture import CultureInput, CultureToolResult
from travel_skill.shared.observability import traced_tool
from travel_skill.shared.season import normalize_season, season_label
from travel_skill.validation import fail, ok_result, require_fields

logger = get_logger("travel_skill.tools.culture")

_SUMMARY_MAX = 400
_PER_QUERY_COUNT = 6
_MAX_PER_BUCKET = 12


def _queries(destination: str, start_date: str, season: str) -> list[tuple[str, str]]:
    """返回 (bucket, query)：bucket 为 closures | events。"""
    year = start_date[:4] if start_date and len(start_date) >= 4 else ""
    season_zh = season_label(season)
    out: list[tuple[str, str]] = [
        ("closures", f"{destination} 博物馆 景点 开放时间 闭馆"),
        ("closures", f"{destination} 景区 临时闭馆 暂停开放"),
    ]
    if season:
        out.append(("events", f"{destination} {year} {season_zh} 活动 展会 节庆".strip()))
    else:
        out.append(("events", f"{destination} {year} 近期 活动 展会 节庆".strip()))
    return out


def _compact(snip: dict[str, Any]) -> dict[str, Any]:
    summary = str(snip.get("summary") or "").strip()
    if len(summary) > _SUMMARY_MAX:
        summary = summary[:_SUMMARY_MAX] + "…"
    return {
        "title": str(snip.get("title") or "").strip(),
        "url": str(snip.get("url") or "").strip(),
        "summary": summary,
        "site": str(snip.get("site") or "").strip(),
        "published": str(snip.get("published") or "").strip(),
    }


@tool(args_schema=CultureInput)
@traced_tool("get_culture")
def get_culture(
    destination: str,
    start_date: str,
    season: str = "",
) -> dict[str, Any]:
    """检索目的地闭馆/开放时间与当地活动线索（博查原始摘要）。

    不做季节过滤；由主模型根据 start_date / 行程判断是否相关。
    成功时返回 closures、events（精简摘要列表）、search_queries、season、source。
    """
    try:
        require_fields(
            {"destination": destination, "start_date": start_date},
            ["destination", "start_date"],
            tool="get_culture",
        )
        season_n = normalize_season(season, start_date)
        query_specs = _queries(destination, start_date, season_n)
        client = BochaClient()
        closures: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        used_queries: list[str] = []

        for bucket, query in query_specs:
            logger.info("博查搜索 bucket=%s query=%s", bucket, query)
            item = client.web_search(query, freshness="oneYear", count=_PER_QUERY_COUNT)
            if not item.get("ok"):
                raise ToolError(item.get("error") or "博查搜索失败", code="upstream_error")
            used_queries.append(query)
            target = closures if bucket == "closures" else events
            for snip in item.get("snippets") or []:
                if len(target) >= _MAX_PER_BUCKET:
                    break
                target.append(_compact(snip))

        return ok_result(
            CultureToolResult(
                ok=True,
                destination=destination,
                closures=closures,
                events=events,
                search_queries=used_queries,
                season=season_n,
                source="bocha",
            )
        )
    except Exception as exc:
        return fail(exc)
