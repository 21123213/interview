"""geocode_places：地名批量转坐标。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from travel_skill.errors import ToolError
from travel_skill.logging_utils import get_logger
from travel_skill.providers.amap import AmapClient
from travel_skill.schemas.geocode import GeocodeInput, GeocodePoint, GeocodeToolResult
from travel_skill.shared.observability import traced_tool
from travel_skill.validation import fail, ok_result, require_fields

logger = get_logger("travel_skill.tools.geocode")


def run_geocode_places(
    destination: str,
    places: list[dict[str, Any]],
    category: str = "poi",
) -> dict[str, Any]:
    """内部实现（供 build_route 等直接调用）。"""
    try:
        require_fields(
            {"destination": destination, "places": places},
            ["destination", "places"],
            tool="geocode_places",
        )
        client = AmapClient()
        points: list[GeocodePoint] = []
        for item in places:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            item_id = item.get("id") or name
            query = f"{destination}{name}"
            result = client.geocode(query, destination)
            points.append(
                GeocodePoint(
                    id=str(item_id),
                    name=name,
                    lat=float(result.get("lat") or 0),
                    lng=float(result.get("lng") or 0),
                    category=category,
                    area=item.get("area") or "",
                    address=result.get("address") or "",
                    geocode_ok=bool(result.get("ok")),
                )
            )
        if not points:
            raise ToolError("places 中无有效地名", code="invalid_params")
        ok_n = sum(1 for p in points if p.geocode_ok)
        logger.info("geocode %s: %d/%d ok", category, ok_n, len(points))
        return ok_result(
            GeocodeToolResult(
                ok=True,
                destination=destination,
                category=category,
                places=points,
            )
        )
    except Exception as exc:
        return fail(exc)


@tool(args_schema=GeocodeInput)
@traced_tool("geocode_places")
def geocode_places(
    destination: str,
    places: list[dict[str, Any]],
    category: str = "poi",
) -> dict[str, Any]:
    """将地名批量转为经纬度（高德地理编码）。

    成功时返回 GeocodeToolResult：ok、destination、category、places[]（id/name/lat/lng/address/geocode_ok）。
    geocode_ok=false 表示该点编码失败。
    """
    return run_geocode_places(destination, places, category=category)
