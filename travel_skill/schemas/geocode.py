"""地理编码：入参 + 出参。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from travel_skill.schemas.common import ToolEnvelope


class PlaceNameItem(BaseModel):
    """待编码的单个地名。"""

    name: str = Field(description="地点名称，必填")
    id: str = Field(default="", description="可选自定义 ID")
    area: str = Field(default="", description="可选片区")


class GeocodeInput(BaseModel):
    """geocode_places 入参。"""

    destination: str = Field(description="城市上下文，如「杭州」，会拼进查询提高准确度")
    places: list[dict[str, Any]] = Field(
        description='地点列表，每项至少含 name，例如 [{"name":"西湖"}]；可选 id、area'
    )
    category: str = Field(
        default="poi",
        description="类别标记：poi=景点 | dining=餐饮 | hotel=酒店",
    )


class GeocodePoint(BaseModel):
    """单个编码结果。"""

    id: str = Field(default="", description="地点 ID")
    name: str = Field(description="名称")
    lat: float = Field(description="纬度")
    lng: float = Field(description="经度")
    category: str = Field(description="类别：poi | dining | hotel")
    area: str = Field(default="", description="片区")
    address: str = Field(default="", description="地址")
    geocode_ok: bool = Field(default=True, description="是否编码成功；false 时坐标可能为 0")


class GeocodeToolResult(ToolEnvelope):
    """geocode_places 完整返回。"""

    destination: str | None = Field(default=None, description="目的地城市")
    category: str = Field(default="", description="本次编码类别")
    places: list[GeocodePoint] = Field(default_factory=list, description="编码结果列表")
