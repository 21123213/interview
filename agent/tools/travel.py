"""内置旅游工具（Agent BaseTool；逻辑在 agent.travel.runners）。"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from agent.tools.base import BaseTool, ToolResult, ToolSpec
from agent.travel import runners


def _wrap(run: Callable[..., dict[str, Any]], **kwargs: Any) -> ToolResult:
    data = run(**kwargs)
    text = json.dumps(data, ensure_ascii=False)
    return ToolResult(ok=bool(data.get("ok")), content=text, data=data)


class GetWeatherTool(BaseTool):
    spec = ToolSpec(
        name="get_weather",
        description="查询目的地多日天气预报及是否适合户外。",
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "城市或目的地"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "days": {"type": "integer", "description": "预报天数"},
            },
            "required": ["destination", "start_date", "days"],
        },
        exec_mode="io",
    )

    def run(self, destination: str = "", start_date: str = "", days: int = 3, **_: Any) -> ToolResult:
        return _wrap(runners.run_get_weather, destination=destination, start_date=start_date, days=days)


class GetCultureTool(BaseTool):
    spec = ToolSpec(
        name="get_culture",
        description=(
            "检索目的地闭馆/开放时间与当地活动原始线索（博查摘要，不做工具内过滤）。"
            "由你根据行程日期判断是否相关。可传 season=春/夏/秋/冬；不传则按 start_date 推断检索词。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "start_date": {"type": "string", "description": "行程开始日期 YYYY-MM-DD"},
                "season": {
                    "type": "string",
                    "description": "可选：春/夏/秋/冬",
                    "default": "",
                },
            },
            "required": ["destination", "start_date"],
        },
        exec_mode="io",
    )

    def run(
        self,
        destination: str = "",
        start_date: str = "",
        season: str = "",
        **_: Any,
    ) -> ToolResult:
        from travel_skill.tools.culture import get_culture as lc_get_culture

        data = lc_get_culture.invoke(
            {
                "destination": destination,
                "start_date": start_date,
                "season": season or "",
            }
        )
        if not isinstance(data, dict):
            return ToolResult(ok=False, content=str(data))
        text = json.dumps(data, ensure_ascii=False)
        return ToolResult(ok=bool(data.get("ok")), content=text, data=data)


class GeocodePlacesTool(BaseTool):
    spec = ToolSpec(
        name="geocode_places",
        description="批量地名转经纬度（高德）。",
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "places": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                        },
                    },
                },
                "category": {"type": "string", "description": "poi 或 dining"},
            },
            "required": ["destination", "places"],
        },
        exec_mode="io",
    )

    def run(
        self,
        destination: str = "",
        places: list | None = None,
        category: str = "poi",
        **_: Any,
    ) -> ToolResult:
        return _wrap(
            runners.run_geocode_places,
            destination=destination,
            places=places or [],
            category=category,
        )


class BuildRouteTool(BaseTool):
    spec = ToolSpec(
        name="build_route",
        description=(
            "将线路/散落景点排入每日日程并地理编码。"
            "itinerary_lines 每项必须含 stops:[{name,role}]（不要用 points）；"
            "loose_pois 仅作末尾补位。itinerary_lines 或 loose_pois 至少一项。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "days": {"type": "integer"},
                "itinerary_lines": {
                    "type": "array",
                    "description": (
                        "完整线路。每项形如 "
                        "{id,title,stops:[{name,role}],heat?}；role=poi|food。"
                        "禁止用 points 代替 stops。"
                    ),
                    "items": {"type": "object"},
                },
                "loose_pois": {
                    "type": "array",
                    "description": "不成线的散落点，排入当天末尾补位",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                    },
                },
                "dining_items": {"type": "array", "items": {"type": "object"}},
                "late_start": {"type": "boolean"},
                "extra_context": {"type": "string"},
            },
            "required": ["destination", "days"],
        },
        exec_mode="local",
    )

    def run(
        self,
        destination: str = "",
        days: int = 1,
        itinerary_lines: list | None = None,
        loose_pois: list | None = None,
        dining_items: list | None = None,
        late_start: bool = False,
        extra_context: str = "",
        **_: Any,
    ) -> ToolResult:
        return _wrap(
            runners.run_build_route,
            destination=destination,
            days=days,
            itinerary_lines=itinerary_lines,
            loose_pois=loose_pois,
            dining_items=dining_items,
            late_start=late_start,
            extra_context=extra_context,
        )


class SearchStayTool(BaseTool):
    spec = ToolSpec(
        name="search_stay",
        description=(
            "按行程锚点搜酒店（优先每日整线首站）；有道旅密钥时走 MCP，否则高德周边。"
            "无真实报价时 price_per_night 为 null，不要编造价格。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "check_in_date": {"type": "string"},
                "stay_nights": {"type": "integer"},
                "daily_routes": {"type": "object", "description": "build_route 返回的 days 包装为 {days:[...]}"},
                "anchors": {"type": "array", "items": {"type": "object"}},
                "tier": {"type": "string", "enum": ["luxury", "comfort", "economy"]},
                "extra_context": {"type": "string"},
            },
            "required": ["destination", "check_in_date", "stay_nights"],
        },
        exec_mode="io",
    )

    def run(
        self,
        destination: str = "",
        check_in_date: str = "",
        stay_nights: int = 1,
        daily_routes: dict | None = None,
        anchors: list | None = None,
        tier: str = "",
        extra_context: str = "",
        **_: Any,
    ) -> ToolResult:
        return _wrap(
            runners.run_search_stay,
            destination=destination,
            check_in_date=check_in_date,
            stay_nights=stay_nights,
            daily_routes=daily_routes,
            anchors=anchors,
            tier=tier,
            extra_context=extra_context,
        )


class PlanTransportTool(BaseTool):
    spec = ToolSpec(
        name="plan_transport",
        description=(
            "酒店到各日景点的市内接驳；城际大交通为占位说明。"
            "hotel 请传 search_stay 返回的 hotel 对象（含 lat/lng）；"
            "若暂缺会自动用行程整线首站作起点，勿向用户追问 hotel 字段。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "出发城市"},
                "destination": {"type": "string", "description": "目的地城市"},
                "daily_routes": {
                    "type": "object",
                    "description": "build_route 的返回（含 days）",
                },
                "hotel": {
                    "type": "object",
                    "description": "search_stay 返回的酒店对象，需含 name/lat/lng",
                },
                "tier": {"type": "string", "enum": ["luxury", "comfort", "economy"]},
                "extra_context": {"type": "string"},
            },
            "required": ["origin", "destination", "daily_routes"],
        },
        exec_mode="io",
    )

    def run(
        self,
        origin: str = "",
        destination: str = "",
        daily_routes: dict | None = None,
        hotel: Any = None,
        tier: str = "comfort",
        extra_context: str = "",
        **_: Any,
    ) -> ToolResult:
        return _wrap(
            runners.run_plan_transport,
            origin=origin,
            destination=destination,
            daily_routes=daily_routes or {},
            hotel=hotel,
            tier=tier,
            extra_context=extra_context,
        )


TRAVEL_TOOLS: List[BaseTool] = [
    GetWeatherTool(),
    GetCultureTool(),
    GeocodePlacesTool(),
    BuildRouteTool(),
    SearchStayTool(),
    PlanTransportTool(),
]


def register_travel_tools(registry) -> None:
    for tool in TRAVEL_TOOLS:
        registry.register(tool)
