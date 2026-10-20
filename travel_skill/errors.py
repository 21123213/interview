"""工具错误：缺参 / 上游失败。"""

from __future__ import annotations

from typing import Any


class ToolError(Exception):
    """Skill 工具统一错误。"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "tool_error",
        missing: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.missing = missing or []
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": self.message,
            "code": self.code,
            "missing": self.missing,
            "details": self.details,
        }
