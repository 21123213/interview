"""工具参数缺失校验（执行前 schema + 执行后 missing_params 捕获）。

不做字段归属表：分类用「有没有上游依赖 / 是否执行前就缺」启发式。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent.tools.registry import ToolRegistry

logger = logging.getLogger("agent.runtime.param_check")

SourceKind = str  # user_gap | upstream_gap | tool_error

# 应由上游工具产出、不应直接向用户追问英文参数名的字段
UPSTREAM_PARAM_FIELDS = frozenset(
    {
        "hotel",
        "daily_routes",
        "itinerary_lines",
        "loose_pois",
        "dining_items",
        "places",
        "anchors",
        "geo_poi",
        "geo_dining",
    }
)


@dataclass
class MissingField:
    tool: str
    call_id: str
    field: str
    description: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParamGap:
    """一次调用上的参数缺口。"""

    tool: str
    call_id: str
    fields: List[MissingField]
    source: SourceKind
    arguments: Dict[str, Any] = field(default_factory=dict)
    tool_description: str = ""


def is_empty_value(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    if val == [] or val == {}:
        return True
    return False


def missing_required_fields(
    registry: ToolRegistry,
    tool_name: str,
    arguments: Optional[Dict[str, Any]],
) -> List[MissingField]:
    """按 JSON Schema required 检查；未知工具返回空（由执行器报 UnknownTool）。"""
    tool = registry.get(tool_name)
    if tool is None:
        return []
    args = arguments or {}
    schema = tool.spec.parameters or {}
    required = schema.get("required") or []
    props = schema.get("properties") or {}
    missing: List[MissingField] = []
    for name in required:
        if not isinstance(name, str):
            continue
        if name not in args or is_empty_value(args.get(name)):
            prop = props.get(name) or {}
            desc = ""
            if isinstance(prop, dict):
                desc = str(prop.get("description") or "").strip()
            missing.append(
                MissingField(
                    tool=tool_name,
                    call_id="",
                    field=name,
                    description=desc or name,
                    arguments=dict(args),
                )
            )
    return missing


def classify_source(
    *,
    has_upstream_dependency: bool,
    before_exec: bool,
    field_names: Optional[List[str]] = None,
) -> SourceKind:
    """无字段表时的分类。

    - 缺的是上游工具产物（hotel/daily_routes 等）→ upstream_gap（勿向用户要英文字段）
    - 有上游步骤依赖且当前仍缺参 → upstream_gap
    - 执行前就缺、且无上游依赖 → 用户问题里没给（user_gap）
    """
    names = {str(n) for n in (field_names or []) if n}
    if names and names.issubset(UPSTREAM_PARAM_FIELDS):
        return "upstream_gap"
    if names & UPSTREAM_PARAM_FIELDS:
        # 混有上游字段时，优先按上游缺口处理，避免暴露 hotel 等内部名
        return "upstream_gap"
    if has_upstream_dependency:
        return "upstream_gap"
    if before_exec:
        return "user_gap"
    return "user_gap"


def parse_tool_error_payload(content: str) -> Optional[Dict[str, Any]]:
    """从工具失败 content 里解析 JSON 载荷（含「工具返回错误:」前缀）。"""
    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("工具返回错误:"):
        text = text[len("工具返回错误:") :].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def is_missing_params_content(content: str) -> bool:
    data = parse_tool_error_payload(content)
    if data is not None and data.get("code") in ("missing_params", "upstream_gap"):
        return True
    return "缺少参数" in (content or "") or "缺少:" in (content or "")


def _field_names_from_error(error: str) -> List[str]:
    """从错误文案里抠已知字段名（如「需要 itinerary_lines 或 loose_pois」）。"""
    text = error or ""
    known = sorted(
        UPSTREAM_PARAM_FIELDS
        | {
            "destination",
            "origin",
            "start_date",
            "check_in_date",
            "stay_nights",
            "days",
            "hotel",
        },
        key=len,
        reverse=True,
    )
    found: List[str] = []
    for name in known:
        if name in text and name not in found:
            found.append(name)
    return found


def gaps_from_failed_tool_results(
    registry: ToolRegistry,
    calls: List[Any],
    results: List[Any],
    *,
    before_exec: bool = False,
) -> List[ParamGap]:
    """把「工具返回 missing_params / upstream_gap」转成 ParamGap。

    与 build_gaps_for_calls（只看 schema required）互补：
    build_route 等工具的 itinerary_lines 不在 required 里，但业务层会返回
    code=missing_params；若只走 schema，post_gaps 会为空并错误地继续跑下游。
    """
    gaps: List[ParamGap] = []
    for call, result in zip(calls, results):
        content = getattr(result, "content", "") or ""
        error_class = getattr(result, "error_class", "") or ""
        ok = bool(getattr(result, "ok", True))
        if not (
            error_class == "MissingParams"
            or ((not ok) and is_missing_params_content(content))
        ):
            continue
        name = getattr(call, "name", "") or ""
        args = dict(getattr(call, "arguments", None) or {})
        cid = getattr(call, "call_id", "") or name
        deps = getattr(call, "depends_on", None)

        # 优先用 schema required 缺口；没有则从错误文案推断
        fields = missing_required_fields(registry, name, args)
        if not fields:
            payload = parse_tool_error_payload(content) or {}
            err = str(payload.get("error") or content)
            names = _field_names_from_error(err) or ["_upstream"]
            fields = [
                MissingField(
                    tool=name,
                    call_id=cid,
                    field=n,
                    description=err[:120],
                    arguments=args,
                )
                for n in names
            ]
        else:
            for f in fields:
                f.call_id = cid

        source = classify_source(
            has_upstream_dependency=bool(deps),
            before_exec=before_exec,
            field_names=[f.field for f in fields],
        )
        # 业务 code=upstream_gap 时强制归类，避免误成 user_gap
        payload = parse_tool_error_payload(content) or {}
        if payload.get("code") == "upstream_gap":
            source = "upstream_gap"

        tool = registry.get(name)
        gaps.append(
            ParamGap(
                tool=name,
                call_id=cid,
                fields=fields,
                source=source,
                arguments=args,
                tool_description=(tool.spec.description if tool else ""),
            )
        )
    return gaps


def build_gaps_for_calls(
    registry: ToolRegistry,
    calls: List[Any],
    *,
    before_exec: bool,
    upstream_ids: Optional[set[str]] = None,
    failed_upstream_ids: Optional[set[str]] = None,
) -> List[ParamGap]:
    """calls 项需有 name/arguments/call_id（ToolCallSpec 或同类）。"""
    gaps: List[ParamGap] = []
    failed_upstream_ids = failed_upstream_ids or set()
    for call in calls:
        name = getattr(call, "name", "") or ""
        args = getattr(call, "arguments", None) or {}
        cid = getattr(call, "call_id", "") or name
        fields = missing_required_fields(registry, name, args)
        if not fields:
            continue
        for f in fields:
            f.call_id = cid
        deps = getattr(call, "depends_on", None)
        has_dep = bool(deps) or (upstream_ids is not None and bool(upstream_ids))
        if failed_upstream_ids and deps:
            has_dep = has_dep or any(d in failed_upstream_ids for d in deps)
        source = classify_source(
            has_upstream_dependency=bool(has_dep),
            before_exec=before_exec,
            field_names=[f.field for f in fields],
        )
        tool = registry.get(name)
        gaps.append(
            ParamGap(
                tool=name,
                call_id=cid,
                fields=fields,
                source=source,
                arguments=dict(args),
                tool_description=(tool.spec.description if tool else ""),
            )
        )
    return gaps
