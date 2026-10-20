"""住宿：入参 + 出参。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from travel_skill.schemas.common import ToolEnvelope

HotelTier = Literal["luxury", "comfort", "economy"]


class StayInput(BaseModel):
    """search_stay 入参。"""

    destination: str = Field(description="目的地城市")
    check_in_date: str = Field(description="入住日期 yyyy-MM-dd")
    stay_nights: int = Field(description="住宿晚数，必须 >= 1", ge=1)
    daily_routes: dict[str, Any] | None = Field(
        default=None,
        description='build_route 结果片段，形如 {"days": [...]}；与 anchors 至少提供其一',
    )
    anchors: list[dict[str, Any]] | None = Field(
        default=None,
        description='显式锚点 [{"day","name","lat","lng"}, ...]；与 daily_routes 至少提供其一',
    )
    tier: str = Field(
        default="",
        description="档位 luxury=豪华 | comfort=舒适 | economy=经济；空则用默认档",
    )
    extra_context: str = Field(default="", description="可选用户原话；为空则忽略")


class GeoPoint(BaseModel):
    id: str = Field(default="", description="地点 ID")
    name: str = Field(description="名称")
    lat: float = Field(description="纬度")
    lng: float = Field(description="经度")
    category: str = Field(description="类别：poi | dining | hotel")
    area: str = Field(default="", description="片区")
    address: str = Field(default="", description="地址")
    geocode_ok: bool = Field(default=True, description="地理编码是否成功")


class HotelOption(BaseModel):
    tier: HotelTier = Field(description="档位：luxury=豪华 | comfort=舒适 | economy=经济")
    name: str = Field(description="酒店名")
    lat: float = Field(description="纬度")
    lng: float = Field(description="经度")
    address: str = Field(default="", description="地址")
    area: str = Field(default="", description="片区说明")
    price_per_night: int = Field(default=0, description="每晚价格（元）")
    star: int = Field(default=0, description="星级")
    amap_id: str = Field(default="", description="高德 POI ID")
    dida_hotel_id: str = Field(default="", description="道旅酒店 ID")
    price_source: str = Field(default="", description="价格来源说明")


class StayResult(BaseModel):
    """内部业务结果（不含外壳）。"""

    destination: str = Field(description="目的地")
    tier: HotelTier = Field(default="comfort", description="选用档位")
    hotel: HotelOption | None = Field(default=None, description="推荐酒店")
    day_anchors: list[dict] = Field(default_factory=list, description="日锚点列表")
    geo_hotels: list[dict] = Field(default_factory=list, description="酒店坐标（供交通工具）")
    source: str = Field(default="", description="数据来源")


class StayToolResult(ToolEnvelope):
    """search_stay 完整返回。"""

    destination: str | None = Field(default=None, description="目的地")
    tier: str = Field(default="", description="选用档位")
    hotel: HotelOption | None = Field(default=None, description="推荐酒店对象")
    day_anchors: list[dict] = Field(default_factory=list, description="使用的日锚点列表")
    geo_hotels: list[dict] = Field(default_factory=list, description="酒店坐标列表，供 plan_transport")
    source: str = Field(default="", description="数据来源，如 dida / amap")
