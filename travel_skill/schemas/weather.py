"""天气：入参 + 出参（含工具外壳）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from travel_skill.schemas.common import ToolEnvelope


class WeatherInput(BaseModel):
    """get_weather 入参。"""

    destination: str = Field(description="目的地城市或区域，如「杭州」")
    start_date: str = Field(description="出发日期，格式 yyyy-MM-dd")
    days: int = Field(description="需要预报的天数，必须 >= 1", ge=1)


class DailyWeather(BaseModel):
    """单日天气。"""

    date: str = Field(description="日期 yyyy-MM-dd")
    condition: str = Field(description="天气现象，如晴/多云/雨")
    temp: str = Field(description="最高/最低温，如 28/22")
    outdoor_ok: bool = Field(description="当天是否适合户外游玩")


class WeatherToolResult(ToolEnvelope):
    """get_weather 完整返回（成功时含下方业务字段）。"""

    destination: str | None = Field(default=None, description="目的地")
    daily: list[DailyWeather] = Field(default_factory=list, description="逐日预报列表")
    summary: str = Field(default="", description="天气一句话摘要")
    location_id: str | None = Field(default=None, description="和风城市定位 ID")
    location_name: str | None = Field(default=None, description="定位城市名")
    source: str = Field(default="", description="数据来源，成功时一般为 qweather")
