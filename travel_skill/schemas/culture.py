"""人文：入参 + 出参（闭馆 / 活动原始检索，供主 Agent LLM 判断时效）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from travel_skill.schemas.common import ToolEnvelope


class CultureInput(BaseModel):
    """get_culture 入参。"""

    destination: str = Field(description="目的地城市或区域")
    start_date: str = Field(description="出发日期 yyyy-MM-dd（用于检索年份上下文）")
    season: str = Field(
        default="",
        description="可选季节：春/夏/秋/冬；为空则按 start_date 月份推断，仅影响活动检索词",
    )


class CultureToolResult(ToolEnvelope):
    """get_culture 完整返回：原始检索线索，不做工具内 LLM 过滤。"""

    destination: str | None = Field(default=None, description="目的地")
    closures: list[dict] = Field(
        default_factory=list,
        description="闭馆/开放时间相关检索摘要（title/url/summary/site/published）",
    )
    events: list[dict] = Field(
        default_factory=list,
        description="当地活动/展会/节庆相关检索摘要",
    )
    search_queries: list[str] = Field(default_factory=list, description="实际使用的搜索词")
    season: str = Field(default="", description="检索用季节：春/夏/秋/冬")
    source: str = Field(default="", description="数据来源，成功时一般为 bocha")
