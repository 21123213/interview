"""plan_transport：大交通占位说明 + 市内段路径。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from travel_skill.errors import ToolError
from travel_skill.logging_utils import get_logger
from travel_skill.providers.amap import AmapClient
from travel_skill.schemas.stay import HotelTier
from travel_skill.schemas.transport import (
    IntercityPlan,
    TransportInput,
    TransportSegment,
    TransportToolResult,
)
from travel_skill.shared.geo_utils import point_dist_km
from travel_skill.shared.observability import traced_tool
from travel_skill.validation import fail, ok_result, require_fields

logger = get_logger("travel_skill.tools.transport")

WALK_THRESHOLD_KM = 0.8
TIER_MODE: dict[HotelTier, str] = {
    "economy": "transit",
    "comfort": "transit",
    "luxury": "driving",
}
DRIVING_COST_PER_KM = 2.5
TRANSIT_COST = 4.0


def _estimate(from_pt: dict[str, Any], to_pt: dict[str, Any], mode: str) -> dict[str, Any]:
    distance_km = point_dist_km(from_pt, to_pt)
    if mode == "walking" or distance_km <= WALK_THRESHOLD_KM:
        mode = "walking"
        speed, cost = 4.5, 0.0
    elif mode == "driving":
        speed, cost = 25.0, round(distance_km * DRIVING_COST_PER_KM, 1)
    else:
        mode = "transit"
        speed, cost = 18.0, TRANSIT_COST
    duration_min = max(5, int((distance_km / speed) * 60))
    labels = {
        "walking": f"步行约 {duration_min} 分钟",
        "transit": f"公交/地铁约 {duration_min} 分钟",
        "driving": f"驾车约 {duration_min} 分钟",
    }
    return {
        "ok": True,
        "mode": mode,
        "duration_min": duration_min,
        "distance_km": round(distance_km, 2),
        "summary": labels[mode],
        "cost_estimate": cost,
        "source": "estimate",
    }


def _plan_segment(
    from_pt: dict[str, Any],
    to_pt: dict[str, Any],
    tier: HotelTier,
    city: str,
    client: AmapClient | None,
) -> TransportSegment:
    distance_km = point_dist_km(from_pt, to_pt)
    preferred = TIER_MODE.get(tier, "transit")
    if distance_km <= WALK_THRESHOLD_KM:
        preferred = "walking"

    result: dict[str, Any] = {"ok": False}
    if client:
        if preferred == "walking":
            result = client.direction_walking(from_pt, to_pt)
        elif preferred == "driving":
            result = client.direction_driving(from_pt, to_pt)
        else:
            result = client.direction_transit(from_pt, to_pt, city)
    if not result.get("ok"):
        result = _estimate(from_pt, to_pt, preferred)

    return TransportSegment(
        from_id=str(from_pt.get("id") or ""),
        from_name=str(from_pt.get("name") or ""),
        to_id=str(to_pt.get("id") or ""),
        to_name=str(to_pt.get("name") or ""),
        mode=result.get("mode", preferred),  # type: ignore[arg-type]
        duration_min=int(result.get("duration_min", 0)),
        distance_km=float(result.get("distance_km", distance_km)),
        cost_estimate=float(result.get("cost_estimate", 0)),
        summary=str(result.get("summary", "")),
        source=str(result.get("source", "amap")),
    )


@tool(args_schema=TransportInput)
@traced_tool("plan_transport")
def plan_transport(
    origin: str,
    destination: str,
    daily_routes: dict[str, Any],
    hotel: dict[str, Any],
    tier: str = "comfort",
    extra_context: str = "",
) -> dict[str, Any]:
    """规划酒店到各日景点的市内接驳；城际大交通仅返回起讫说明占位。

    成功时返回 TransportToolResult：ok、intercity、segments、daily_summaries、
    total_commute_min、total_cost_estimate、source。大交通无真实票价时刻。
    """
    try:
        require_fields(
            {
                "origin": origin,
                "destination": destination,
                "daily_routes": daily_routes,
                "hotel": hotel,
            },
            ["origin", "destination", "daily_routes", "hotel"],
            tool="plan_transport",
        )
        _ = extra_context
        days = daily_routes.get("days") or []
        if not days:
            raise ToolError("daily_routes.days 为空", code="missing_params", missing=["daily_routes.days"])
        if not (hotel.get("lat") or hotel.get("lng")):
            raise ToolError("hotel 缺少 lat/lng", code="missing_params", missing=["hotel.lat", "hotel.lng"])

        use_tier: HotelTier = (tier or "comfort")  # type: ignore[assignment]
        if use_tier not in ("luxury", "comfort", "economy"):
            use_tier = "comfort"

        intercity = IntercityPlan(
            mode="高铁/航班待确认",
            summary=f"{origin} → {destination}",
            note="大交通时刻与票价未接入本工具，请结合时刻表查询",
            source="placeholder",
        )

        client: AmapClient | None = None
        try:
            client = AmapClient()
        except Exception as exc:
            logger.warning("高德不可用，市内段使用距离估算: %s", exc)

        hotel_pt = {
            "id": hotel.get("id") or "hotel",
            "name": hotel.get("name") or "酒店",
            "lat": float(hotel.get("lat") or 0),
            "lng": float(hotel.get("lng") or 0),
        }
        segments: list[TransportSegment] = []
        daily_summaries: list[str] = []

        for day in days:
            stops = day.get("stops") or []
            day_num = day.get("day", 0)
            prev = hotel_pt
            parts: list[str] = []
            for stop in stops:
                stop_pt = {
                    "id": stop.get("id", ""),
                    "name": stop.get("name", ""),
                    "lat": float(stop.get("lat") or 0),
                    "lng": float(stop.get("lng") or 0),
                }
                if not (stop_pt["lat"] or stop_pt["lng"]):
                    continue
                seg = _plan_segment(prev, stop_pt, use_tier, destination, client)
                segments.append(seg)
                parts.append(f"{seg.from_name}→{seg.to_name} {seg.summary}")
                prev = stop_pt
            daily_summaries.append(f"D{day_num}: " + ("；".join(parts[:3]) if parts else "无行程"))

        return ok_result(
            TransportToolResult(
                ok=True,
                intercity=intercity,
                segments=segments,
                daily_summaries=daily_summaries,
                total_commute_min=sum(s.duration_min for s in segments),
                total_cost_estimate=round(sum(s.cost_estimate for s in segments), 1),
                source="amap" if client else "estimate",
            )
        )
    except Exception as exc:
        return fail(exc)
