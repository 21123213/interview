"""交通：入参 + 出参。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from travel_skill.schemas.common import ToolEnvelope

TransportMode = Literal["transit", "driving", "walking", "intercity"]
HotelTier = Literal["luxury", "comfort", "economy"]


class TransportInput(BaseModel):
    """plan_transport 入参。"""

    origin: str = Field(description="出发城市（用于大交通摘要）")
    destination: str = Field(description="目的地城市")
    daily_routes: dict[str, Any] = Field(
        description='build_route 结果，需含 {"days": [...]}，stops 最好已有 lat/lng'
    )
    hotel: dict[str, Any] = Field(description="search_stay 的酒店，至少含 name、lat、lng")
    tier: str = Field(
        default="comfort",
        description="luxury|comfort|economy，影响更偏公交还是驾车",
    )
    extra_context: str = Field(default="", description="可选用户原话；为空则忽略")


class TransportSegment(BaseModel):
    from_id: str = Field(default="", description="起点 ID")
    from_name: str = Field(default="", description="起点名称")
    to_id: str = Field(default="", description="终点 ID")
    to_name: str = Field(default="", description="终点名称")
    mode: TransportMode = Field(
        default="transit",
        description="方式：transit=公交地铁 | driving=驾车 | walking=步行 | intercity=城际",
    )
    duration_min: int = Field(default=0, description="耗时分钟")
    distance_km: float = Field(default=0.0, description="距离公里")
    cost_estimate: float = Field(default=0.0, description="费用粗估（元）")
    summary: str = Field(default="", description="路段摘要")
    source: str = Field(default="amap", description="路径来源")


class IntercityPlan(BaseModel):
    mode: str = Field(default="待确认", description="大交通方式说明")
    summary: str = Field(default="", description="起讫摘要")
    duration_min: int | None = Field(default=None, description="时长（未接入时为 null）")
    cost_estimate: float | None = Field(default=None, description="费用（未接入时为 null）")
    source: str = Field(default="placeholder", description="占位来源标记")
    note: str = Field(
        default="大交通时刻/票价未接入，仅提供起讫说明",
        description="补充说明",
    )


class TransportResult(BaseModel):
    intercity: IntercityPlan = Field(description="城际大交通（占位）")
    segments: list[TransportSegment] = Field(default_factory=list, description="市内路段")
    daily_summaries: list[str] = Field(default_factory=list, description="按天交通摘要")
    total_commute_min: int = Field(default=0, description="市内总耗时分钟")
    total_cost_estimate: float = Field(default=0.0, description="市内费用粗估")
    source: str = Field(default="amap", description="数据来源")


class TransportToolResult(ToolEnvelope):
    """plan_transport 完整返回。"""

    intercity: IntercityPlan | None = Field(default=None, description="城际大交通占位对象")
    segments: list[TransportSegment] = Field(default_factory=list, description="市内路段列表")
    daily_summaries: list[str] = Field(default_factory=list, description="按天交通摘要")
    total_commute_min: int = Field(default=0, description="市内总耗时分钟")
    total_cost_estimate: float = Field(default=0.0, description="市内费用粗估（元）")
    source: str = Field(default="", description="amap 或 estimate")
