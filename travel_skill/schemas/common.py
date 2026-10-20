"""工具统一外壳字段。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolEnvelope(BaseModel):
    """所有工具返回的公共外壳（成功/失败都带）。"""

    ok: bool = Field(description="是否成功")
    error: str | None = Field(default=None, description="失败原因；成功时为 null")
    code: str = Field(
        default="",
        description="错误码：空字符串表示成功；常见 missing_params / upstream_error / llm_error / empty_result / runtime_error",
    )
    missing: list[str] = Field(
        default_factory=list,
        description="缺失的必填参数名列表；成功时为空列表",
    )
    details: dict = Field(default_factory=dict, description="额外错误细节；一般可忽略")
