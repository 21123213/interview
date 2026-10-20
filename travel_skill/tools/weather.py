"""get_weather：目的地多日预报。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from travel_skill.errors import ToolError
from travel_skill.logging_utils import get_logger
from travel_skill.providers.qweather import fetch_weather_bundle
from travel_skill.schemas.weather import DailyWeather, WeatherInput, WeatherToolResult
from travel_skill.shared.observability import traced_tool
from travel_skill.validation import fail, ok_result, require_fields

logger = get_logger("travel_skill.tools.weather")

_OUTDOOR_BAD = ("雨", "雪", "暴", "雷", "冰雹", "沙尘")


def _outdoor_ok(condition: str) -> bool:
    return not any(k in condition for k in _OUTDOOR_BAD)


def _parse_daily(bundle: dict[str, Any], days: int, start_date: str) -> list[DailyWeather]:
    daily_data = (bundle.get("daily_forecast") or {}).get("data") or {}
    rows = daily_data.get("daily") or []
    if start_date:
        filtered = [r for r in rows if r.get("fxDate", "") >= start_date]
        if filtered:
            rows = filtered
    out: list[DailyWeather] = []
    for row in rows[:days]:
        condition = row.get("textDay") or row.get("textNight") or "未知"
        out.append(
            DailyWeather(
                date=row.get("fxDate", ""),
                condition=condition,
                temp=f"{row.get('tempMax', '')}/{row.get('tempMin', '')}",
                outdoor_ok=_outdoor_ok(condition),
            )
        )
    return out


@tool(args_schema=WeatherInput)
@traced_tool("get_weather")
def get_weather(
    destination: str,
    start_date: str,
    days: int,
) -> dict[str, Any]:
    """查询目的地多日天气预报，判断是否适合户外。

    成功时返回 WeatherToolResult 字段：ok、destination、summary、daily[]（date/condition/temp/outdoor_ok）、
    location_id、location_name、source。失败时 ok=false，并带 error、code、missing。
    """
    try:
        require_fields(
            {"destination": destination, "start_date": start_date, "days": days},
            ["destination", "start_date", "days"],
            tool="get_weather",
        )
        days_n = int(days)
        if days_n < 1:
            raise ToolError("days 必须 >= 1", code="invalid_params")

        logger.info("get_weather destination=%s days=%s start=%s", destination, days_n, start_date)
        bundle = fetch_weather_bundle(destination)
        if not bundle.get("ok"):
            raise ToolError(bundle.get("error") or "天气 API 失败", code="upstream_error")

        daily = _parse_daily(bundle, days_n, start_date)
        if not daily:
            raise ToolError("API 未返回可用日预报", code="empty_result")

        location = bundle.get("location") or {}
        conditions = [d.condition for d in daily]
        summary = f"{destination} {daily[0].date} 起 {len(daily)} 天：" + "、".join(conditions[:3])
        return ok_result(
            WeatherToolResult(
                ok=True,
                destination=destination,
                daily=daily,
                summary=summary,
                location_id=location.get("id"),
                location_name=location.get("name"),
                source="qweather",
            )
        )
    except Exception as exc:
        return fail(exc)
