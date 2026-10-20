"""入口必填校验与返回组装。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from travel_skill.errors import ToolError


def require_fields(payload: dict[str, Any], fields: list[str], *, tool: str) -> None:
    missing: list[str] = []
    for name in fields:
        val = payload.get(name)
        if val is None:
            missing.append(name)
        elif isinstance(val, str) and not val.strip():
            missing.append(name)
        elif isinstance(val, (list, dict)) and not val:
            missing.append(name)
    if missing:
        raise ToolError(
            f"{tool} 缺少必填参数: {', '.join(missing)}",
            code="missing_params",
            missing=missing,
        )


def ok_result(model: BaseModel) -> dict[str, Any]:
    """成功返回：序列化带中文 Field 注释的结果模型。"""
    data = model.model_dump()
    data["ok"] = True
    data["error"] = None
    data.setdefault("code", "")
    data.setdefault("missing", [])
    data.setdefault("details", {})
    return data


def fail(exc: BaseException) -> dict[str, Any]:
    """失败返回：统一外壳。"""
    if isinstance(exc, ToolError):
        return exc.to_dict()
    return {
        "ok": False,
        "error": str(exc),
        "code": "runtime_error",
        "missing": [],
        "details": {},
    }


# 兼容旧名
def ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "error": None, "code": "", "missing": [], "details": {}, **data}
