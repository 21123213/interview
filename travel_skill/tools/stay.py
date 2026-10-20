"""search_stay：按日锚点搜酒店。"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from travel_skill.errors import ToolError
from travel_skill.logging_utils import get_logger
from travel_skill.shared.observability import traced_tool
from travel_skill.providers.amap import AmapClient, TIER_KEYWORDS
from travel_skill.providers.dida_client import (
    DidaHotelClient,
    TIER_STAR_INT,
    parse_hotel_fields,
    parse_hotel_price,
)
from travel_skill.schemas.stay import HotelOption, HotelTier, StayInput, StayToolResult
from travel_skill.shared.config import DEFAULT_HOTEL_TIER, DUTU_API_KEY
from travel_skill.validation import fail, ok_result, require_fields

logger = get_logger("travel_skill.tools.stay")

TIER_DEFAULT_PRICES: dict[HotelTier, int] = {
    "luxury": 1200,
    "comfort": 450,
    "economy": 200,
}


def _day_anchors(daily_routes: dict[str, Any]) -> list[dict[str, Any]]:
    days = daily_routes.get("days") or []
    anchors: list[dict[str, Any]] = []
    for day in days:
        for stop in day.get("stops") or []:
            if stop.get("type") == "hotel":
                continue
            lat, lng = float(stop.get("lat") or 0), float(stop.get("lng") or 0)
            if lat or lng:
                anchors.append(
                    {
                        "day": day.get("day"),
                        "name": stop.get("name", ""),
                        "lat": lat,
                        "lng": lng,
                    }
                )
                break
    return anchors


def _fetch_via_dida(
    *,
    tier: HotelTier,
    destination: str,
    area_name: str,
    check_in_date: str,
    stay_nights: int,
    fallback_names: list[str],
) -> HotelOption | None:
    client = DidaHotelClient()
    star = TIER_STAR_INT[tier]
    origin = f"{destination}{TIER_KEYWORDS[tier]}"
    plans = [(area_name, "区/县"), (area_name, "景点"), (destination, "城市")]
    for n in fallback_names[:3]:
        plans.append((n, "景点"))

    for place, place_type in plans:
        if not place:
            continue
        try:
            hotels = client.search_hotels(
                place=place,
                place_type=place_type,
                origin_query=origin,
                check_in_date=check_in_date,
                stay_nights=stay_nights,
                tier=tier,
                size=3,
            )
        except Exception as exc:
            logger.warning("道旅 searchHotels 失败 place=%s: %s", place, exc)
            continue
        if not hotels:
            continue
        parsed = parse_hotel_fields(hotels[0])
        price = parsed["price_per_night"]
        price_source = "dida"
        if parsed["hotel_id"]:
            try:
                detail = client.get_hotel_detail(
                    parsed["hotel_id"],
                    check_in_date=check_in_date,
                    stay_nights=stay_nights,
                )
                detail_price = parse_hotel_price(detail)
                if detail_price:
                    price = detail_price
                    price_source = "dida+detail"
            except Exception as exc:
                logger.warning("道旅 getHotelDetail 失败: %s", exc)
        if not price:
            price = TIER_DEFAULT_PRICES[tier]
        return HotelOption(
            tier=tier,
            name=parsed["name"] or f"{place}{TIER_KEYWORDS[tier]}",
            lat=parsed["lat"],
            lng=parsed["lng"],
            address=parsed["address"],
            area=area_name,
            price_per_night=price,
            star=parsed["star"] or star,
            dida_hotel_id=parsed["hotel_id"],
            price_source=price_source,
        )
    return None


@tool(args_schema=StayInput)
@traced_tool("search_stay")
def search_stay(
    destination: str,
    check_in_date: str,
    stay_nights: int,
    daily_routes: dict[str, Any] | None = None,
    anchors: list[dict[str, Any]] | None = None,
    tier: str = "",
    extra_context: str = "",
) -> dict[str, Any]:
    """按每日路线锚点附近搜索酒店（默认以第 1 天起点为中心）。

    成功时返回 StayToolResult：ok、destination、tier、hotel（name/lat/lng/price_per_night 等）、
    day_anchors、geo_hotels、source。
    """
    try:
        require_fields(
            {
                "destination": destination,
                "check_in_date": check_in_date,
                "stay_nights": stay_nights,
            },
            ["destination", "check_in_date", "stay_nights"],
            tool="search_stay",
        )
        _ = extra_context
        use_tier: HotelTier = (tier or DEFAULT_HOTEL_TIER)  # type: ignore[assignment]
        if use_tier not in ("luxury", "comfort", "economy"):
            use_tier = "comfort"

        anchor_list = list(anchors or [])
        if not anchor_list and daily_routes:
            anchor_list = _day_anchors(daily_routes)
        if not anchor_list:
            raise ToolError(
                "search_stay 需要 daily_routes 或 anchors",
                code="missing_params",
                missing=["daily_routes|anchors"],
            )

        primary = anchor_list[0]
        area_name = f"近{primary.get('name') or '日行程起点'}"
        nights = max(int(stay_nights), 1)
        fallback_names = [str(a.get("name") or "") for a in anchor_list if a.get("name")]

        hotel: HotelOption | None = None
        source = ""
        if DUTU_API_KEY:
            try:
                hotel = _fetch_via_dida(
                    tier=use_tier,
                    destination=destination,
                    area_name=area_name,
                    check_in_date=check_in_date,
                    stay_nights=nights,
                    fallback_names=fallback_names,
                )
                if hotel:
                    source = hotel.price_source or "dida"
            except Exception as exc:
                logger.warning("道旅不可用，回退高德: %s", exc)

        if hotel is None:
            amap = AmapClient()
            search = amap.search_hotels_near(
                float(primary["lat"]),
                float(primary["lng"]),
                use_tier,
                destination,
            )
            if search.get("ok"):
                h = search["hotel"]
                hotel = HotelOption(
                    tier=use_tier,
                    name=h["name"],
                    lat=h["lat"],
                    lng=h["lng"],
                    address=h.get("address", ""),
                    area=area_name,
                    price_per_night=TIER_DEFAULT_PRICES[use_tier],
                    amap_id=h.get("amap_id", ""),
                    star=TIER_STAR_INT[use_tier],
                    price_source="amap_estimate",
                )
                source = "amap"
            else:
                raise ToolError(search.get("error") or "未找到酒店", code="empty_result")

        geo_hotels = [
            {
                "id": f"hotel_{use_tier}",
                "name": hotel.name,
                "lat": hotel.lat,
                "lng": hotel.lng,
                "category": "hotel",
                "address": hotel.address,
            }
        ]
        return ok_result(
            StayToolResult(
                ok=True,
                destination=destination,
                tier=use_tier,
                hotel=hotel,
                day_anchors=anchor_list,
                geo_hotels=geo_hotels,
                source=source,
            )
        )
    except Exception as exc:
        return fail(exc)
