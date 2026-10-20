"""build_route：整线入天（仅一套排期）+ geocode。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from travel_skill.errors import ToolError
from travel_skill.logging_utils import get_logger
from travel_skill.schemas.route import RouteDay, RouteInput, RouteStop, RouteToolResult
from travel_skill.shared.observability import traced_tool
from travel_skill.tools.geocode import run_geocode_places
from travel_skill.validation import fail, ok_result, require_fields

logger = get_logger("travel_skill.tools.route")


def _collect_names(
    itinerary_lines: list[dict[str, Any]],
    loose_pois: list[dict[str, Any]],
    dining_items: list[dict[str, Any]],
) -> tuple[list[dict], list[dict]]:
    pois: list[dict[str, Any]] = []
    dinings: list[dict[str, Any]] = []
    seen: set[str] = set()

    for ln in itinerary_lines:
        for st in ln.get("stops") or []:
            name = (st.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            if (st.get("role") or "poi") == "food":
                dinings.append({"id": f"food_{name}", "name": name})
            else:
                pois.append({"id": f"poi_{name}", "name": name, "line_id": ln.get("id", "")})

    for p in loose_pois:
        name = (p.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        pois.append({"id": p.get("id") or f"poi_{name}", "name": name})

    for d in dining_items:
        name = (d.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        dinings.append({"id": d.get("id") or f"food_{name}", "name": name})

    return pois, dinings


def _index(points: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p.get("name", ""): p for p in points if p.get("name")}


def _dedupe_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for ln in lines:
        title = (ln.get("title") or ln.get("id") or "").strip()
        names = tuple(
            (s.get("name") or "").strip()
            for s in (ln.get("stops") or [])
            if (s.get("role") or "poi") != "food"
        )
        key = title or str(names)
        if key in seen_titles:
            continue
        seen_titles.add(key)
        out.append(ln)
    return out


def _schedule_one(
    lines: list[dict[str, Any]],
    loose: list[dict[str, Any]],
    days: int,
    geo_poi: dict[str, dict],
    geo_dining: dict[str, dict],
    late_start: bool,
) -> tuple[list[RouteDay], list[str]]:
    by_heat = sorted(lines, key=lambda x: float(x.get("heat") or 0), reverse=True)
    queue = list(by_heat)
    used_names: set[str] = set()
    day_plans: list[RouteDay] = []
    unused: list[str] = []

    for day_i in range(1, days + 1):
        stops: list[RouteStop] = []
        summary_parts: list[str] = []
        if queue:
            ln = queue.pop(0)
            summary_parts.append(ln.get("title") or ln.get("id") or "线路")
            slot_cycle = ["am", "pm", "eve"]
            si = 0
            for st in ln.get("stops") or []:
                name = (st.get("name") or "").strip()
                if not name:
                    continue
                role = st.get("role") or "poi"
                if role != "food" and name in used_names:
                    continue
                if role != "food":
                    used_names.add(name)
                g = geo_dining.get(name) if role == "food" else geo_poi.get(name)
                g = g or {}
                slot = "lunch" if role == "food" else slot_cycle[min(si, len(slot_cycle) - 1)]
                if role != "food":
                    si += 1
                stops.append(
                    RouteStop(
                        id=str(g.get("id") or name),
                        name=name,
                        type="dining" if role == "food" else "poi",
                        slot=slot,  # type: ignore[arg-type]
                        lat=float(g.get("lat") or 0),
                        lng=float(g.get("lng") or 0),
                        duration_min=60 if role == "food" else 120,
                        reason=f"整线:{ln.get('id', '')}",
                    )
                )
        # 每天最多补一个散落点
        for p in loose:
            name = (p.get("name") or "").strip()
            if not name or name in used_names:
                continue
            used_names.add(name)
            g = geo_poi.get(name) or {}
            stops.append(
                RouteStop(
                    id=str(g.get("id") or name),
                    name=name,
                    type="poi",
                    slot="pm",
                    lat=float(g.get("lat") or 0),
                    lng=float(g.get("lng") or 0),
                    duration_min=90,
                    reason="散落补位",
                )
            )
            summary_parts.append(f"+{name}")
            break

        day_plans.append(
            RouteDay(
                day=day_i,
                start_time="10:00" if late_start else "09:30",
                stops=stops,
                summary="；".join(summary_parts) or f"D{day_i}",
            )
        )

    unused = [str(ln.get("id") or "") for ln in queue if ln.get("id")]
    return day_plans, unused


@tool(args_schema=RouteInput)
@traced_tool("build_route")
def build_route(
    destination: str,
    days: int,
    itinerary_lines: list[dict[str, Any]] | None = None,
    loose_pois: list[dict[str, Any]] | None = None,
    dining_items: list[dict[str, Any]] | None = None,
    late_start: bool = False,
    extra_context: str = "",
) -> dict[str, Any]:
    """将游玩线路排入各天（只产出一套日程），并自动地理编码。

    成功时返回 RouteToolResult：ok、days[]（day/start_time/summary/stops）、
    geo_poi、geo_dining、unused_line_ids、source。stops 含 type/slot/lat/lng。
    注意：只返回一套排期，不做多方案对比。
    """
    try:
        require_fields(
            {"destination": destination, "days": days},
            ["destination", "days"],
            tool="build_route",
        )
        lines = list(itinerary_lines or [])
        loose = list(loose_pois or [])
        dining = list(dining_items or [])
        if not lines and not loose:
            raise ToolError(
                "build_route 需要 itinerary_lines 或 loose_pois",
                code="missing_params",
                missing=["itinerary_lines|loose_pois"],
            )
        days_n = max(int(days), 1)
        use_late = bool(late_start)
        if not use_late and extra_context:
            use_late = any(k in extra_context for k in ("不要早起", "不早起", "晚出发"))

        logger.info(
            "build_route destination=%s days=%d lines=%d loose=%d ctx=%s",
            destination,
            days_n,
            len(lines),
            len(loose),
            bool(extra_context),
        )

        poi_names, dining_names = _collect_names(lines, loose, dining)
        geo_poi_list: list[dict] = []
        geo_dining_list: list[dict] = []
        if poi_names:
            geo_res = run_geocode_places(destination, poi_names, category="poi")
            if not geo_res.get("ok"):
                raise ToolError(geo_res.get("error") or "poi geocode 失败", code="upstream_error")
            geo_poi_list = geo_res.get("places") or []
        if dining_names:
            geo_res = run_geocode_places(destination, dining_names, category="dining")
            if not geo_res.get("ok"):
                raise ToolError(geo_res.get("error") or "dining geocode 失败", code="upstream_error")
            geo_dining_list = geo_res.get("places") or []

        lines = _dedupe_lines(lines)
        day_plans, unused = _schedule_one(
            lines,
            loose,
            days_n,
            _index(geo_poi_list),
            _index(geo_dining_list),
            use_late,
        )
        return ok_result(
            RouteToolResult(
                ok=True,
                days=day_plans,
                geo_poi=geo_poi_list,
                geo_dining=geo_dining_list,
                unused_line_ids=unused,
                source="lines+geocode",
            )
        )
    except Exception as exc:
        return fail(exc)
