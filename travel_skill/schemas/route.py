"""路线排期：入参 + 出参。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from travel_skill.schemas.common import ToolEnvelope

StopType = Literal["poi", "dining", "hotel"]
StopSlot = Literal["am", "lunch", "pm", "eve"]


class RouteInput(BaseModel):
    """build_route 入参。"""

    destination: str = Field(description="目的地城市或区域")
    days: int = Field(description="游玩天数，必须 >= 1", ge=1)
    itinerary_lines: list[dict[str, Any]] | None = Field(
        default=None,
        description="完整线路（由主模型从 web_search/xhs_search 整理）；与 loose_pois 至少提供其一",
    )
    loose_pois: list[dict[str, Any]] | None = Field(
        default=None,
        description="散落点（由主模型整理）；与 itinerary_lines 至少提供其一",
    )
    dining_items: list[dict[str, Any]] | None = Field(
        default=None,
        description="可选餐饮列表，会一并编码坐标",
    )
    late_start: bool = Field(default=False, description="true 时每日约 10:00 出发，否则约 09:30")
    extra_context: str = Field(
        default="",
        description="可选用户原话；若含「不早起」等可按晚出发处理",
    )


class RouteStop(BaseModel):
    id: str = Field(description="站点 ID")
    name: str = Field(description="地点名")
    type: StopType = Field(description="poi=景点 | dining=餐饮 | hotel=酒店")
    slot: StopSlot = Field(description="时段：am=上午 | lunch=午餐 | pm=下午 | eve=晚间")
    lat: float = Field(default=0.0, description="纬度")
    lng: float = Field(default=0.0, description="经度")
    duration_min: int = Field(default=90, description="建议停留分钟")
    reason: str = Field(default="", description="编排理由")


class RouteDay(BaseModel):
    day: int = Field(description="第几天，从 1 起")
    start_time: str = Field(default="09:30", description="出发时刻")
    stops: list[RouteStop] = Field(default_factory=list, description="当日停靠点")
    summary: str = Field(default="", description="当日摘要")


# 内部排期仍用
class RouteResult(BaseModel):
    days: list[RouteDay] = Field(default_factory=list, description="逐日行程（仅一套）")
    geo_poi: list[dict] = Field(default_factory=list, description="景点坐标列表")
    geo_dining: list[dict] = Field(default_factory=list, description="餐饮坐标列表")
    unused_line_ids: list[str] = Field(default_factory=list, description="未排入的线路 ID")
    source: str = Field(default="lines+geocode", description="数据来源")


class RouteToolResult(ToolEnvelope):
    """build_route 完整返回（只产出一套日程）。"""

    days: list[RouteDay] = Field(default_factory=list, description="按天行程列表")
    geo_poi: list[dict] = Field(default_factory=list, description="已编码的景点坐标")
    geo_dining: list[dict] = Field(default_factory=list, description="已编码的餐饮坐标")
    unused_line_ids: list[str] = Field(default_factory=list, description="天数不够未能排入的线路 id")
    source: str = Field(default="", description="数据来源，成功时一般为 lines+geocode")
