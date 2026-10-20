"""旅游工具业务逻辑（纯 dict 返回，ok/error 外壳）。"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from agent.clients.dida_mcp import (
    DidaHotelClient,
    TIER_STAR_INT,
    parse_hotel_fields,
    parse_hotel_price,
)
from agent.travel.clients.amap import AmapClient, TIER_KEYWORDS
from agent.travel.clients.bocha import BochaClient
from agent.travel.clients.qweather import fetch_weather_bundle
from agent.travel.config import (
    DEFAULT_HOTEL_TIER,
    DUTU_API_KEY,
    STAY_HOTEL_SEARCH_RADIUS,
)
from agent.travel.geo import point_dist_km

logger = logging.getLogger("agent.travel.runners")

HotelTier = Literal["luxury", "comfort", "economy"]
_OUTDOOR_BAD = ("雨", "雪", "暴", "雷", "冰雹", "沙尘")

def _ok(**data: Any) -> dict[str, Any]:
    return {"ok": True, "error": None, "code": "", **data}


def _fail(msg: str, code: str = "runtime_error", **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": msg, "code": code, **extra}


def _require(payload: dict[str, Any], fields: list[str], tool: str) -> None:
    missing = []
    for name in fields:
        val = payload.get(name)
        if val is None or (isinstance(val, str) and not val.strip()) or val == [] or val == {}:
            missing.append(name)
    if missing:
        raise ValueError(f"{tool} 缺少: {', '.join(missing)}")


def run_get_weather(destination: str, start_date: str, days: int) -> dict[str, Any]:
    try:
        _require(
            {"destination": destination, "start_date": start_date, "days": days},
            ["destination", "start_date", "days"],
            "get_weather",
        )
        days_n = int(days)
        if days_n < 1:
            return _fail("days 必须 >= 1", "invalid_params")
        bundle = fetch_weather_bundle(destination)
        if not bundle.get("ok"):
            return _fail(bundle.get("error") or "天气失败", "upstream_error")
        rows = ((bundle.get("daily_forecast") or {}).get("data") or {}).get("daily") or []
        if start_date:
            filtered = [r for r in rows if r.get("fxDate", "") >= start_date]
            if filtered:
                rows = filtered
        daily = []
        for row in rows[:days_n]:
            cond = row.get("textDay") or row.get("textNight") or "未知"
            outdoor_ok = not any(k in cond for k in _OUTDOOR_BAD)
            daily.append(
                {
                    "date": row.get("fxDate", ""),
                    "condition": cond,
                    "temp": f"{row.get('tempMax', '')}/{row.get('tempMin', '')}",
                    "outdoor_ok": outdoor_ok,
                }
            )
        if not daily:
            return _fail("无可用预报", "empty_result")
        loc = bundle.get("location") or {}
        summary = f"{destination} {daily[0]['date']} 起 {len(daily)} 天：" + "、".join(
            d["condition"] for d in daily[:3]
        )
        return _ok(
            destination=destination,
            daily=daily,
            summary=summary,
            location_id=loc.get("id"),
            location_name=loc.get("name"),
            source="qweather",
        )
    except ValueError as exc:
        return _fail(str(exc), "missing_params")
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))


_HOLIDAY = ("节", "假", "休", "调休", "国庆", "春节")
_CLOSURE = ("闭馆", "暂停", "关闭", "周一", "维护")
_ETIQUETTE = ("礼仪", "注意", "习俗", "文明", "禁止")
_EVENT = ("活动", "展会", "音乐节", "庙会", "民俗")


def _pick(texts: list[str], keywords: tuple[str, ...], limit: int = 5) -> list[str]:
    picked: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not any(k in text for k in keywords):
            continue
        snippet = re.sub(r"\s+", " ", text.strip())
        if snippet and snippet not in seen:
            seen.add(snippet)
            picked.append(snippet)
        if len(picked) >= limit:
            break
    return picked


def run_get_culture(
    destination: str,
    start_date: str,
    season: str = "",
) -> dict[str, Any]:
    """委托 travel_skill.get_culture（闭馆/活动原始检索）。"""
    try:
        _require(
            {"destination": destination, "start_date": start_date},
            ["destination", "start_date"],
            "get_culture",
        )
        from travel_skill.tools.culture import get_culture as lc_get_culture

        data = lc_get_culture.invoke(
            {
                "destination": destination,
                "start_date": start_date,
                "season": season or "",
            }
        )
        if isinstance(data, dict):
            return data
        return _fail(str(data))
    except ValueError as exc:
        return _fail(str(exc), "missing_params")
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))


def run_geocode_places(
    destination: str,
    places: list[dict[str, Any]],
    category: str = "poi",
) -> dict[str, Any]:
    try:
        _require({"destination": destination, "places": places}, ["destination", "places"], "geocode_places")
        client = AmapClient()
        out: list[dict[str, Any]] = []
        for item in places:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            item_id = item.get("id") or name
            result = client.geocode(f"{destination}{name}", destination)
            out.append(
                {
                    "id": str(item_id),
                    "name": name,
                    "lat": float(result.get("lat") or 0),
                    "lng": float(result.get("lng") or 0),
                    "category": category,
                    "area": item.get("area") or "",
                    "address": result.get("address") or "",
                    "geocode_ok": bool(result.get("ok")),
                }
            )
        if not out:
            return _fail("places 无有效地名", "invalid_params")
        return _ok(destination=destination, category=category, places=out)
    except ValueError as exc:
        return _fail(str(exc), "missing_params")
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))


def _normalize_itinerary_lines(lines: list[dict]) -> list[dict]:
    """兼容模型误传 points / name 字段，统一成 title + stops。"""
    out: list[dict] = []
    for i, ln in enumerate(lines):
        if not isinstance(ln, dict):
            continue
        row = dict(ln)
        if not str(row.get("title") or "").strip() and row.get("name"):
            row["title"] = str(row.get("name") or "")
        if not str(row.get("id") or "").strip():
            row["id"] = f"line_{i + 1}"
        stops_in = row.get("stops")
        if not stops_in:
            stops_in = row.get("points") or row.get("pois") or []
        stops_out: list[dict] = []
        for st in stops_in or []:
            if isinstance(st, str):
                name = st.strip()
                if name:
                    stops_out.append({"name": name, "role": "poi", "note": ""})
            elif isinstance(st, dict):
                name = str(st.get("name") or "").strip()
                if name:
                    stops_out.append(
                        {
                            "name": name,
                            "role": str(st.get("role") or "poi"),
                            "note": str(st.get("note") or ""),
                        }
                    )
        row["stops"] = stops_out
        row.pop("points", None)
        row.pop("pois", None)
        out.append(row)
    return out


def _line_stop_count(lines: list[dict]) -> int:
    return sum(len(ln.get("stops") or []) for ln in lines)


def _collect_route_names(
    lines: list[dict],
    loose: list[dict],
    dining: list[dict],
) -> tuple[list[dict], list[dict]]:
    pois: list[dict] = []
    dinings: list[dict] = []
    seen: set[str] = set()
    for ln in lines:
        for st in ln.get("stops") or []:
            name = (st.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            if (st.get("role") or "poi") == "food":
                dinings.append({"id": f"food_{name}", "name": name})
            else:
                pois.append({"id": f"poi_{name}", "name": name})
    for p in loose:
        name = (p.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            pois.append({"id": p.get("id") or f"poi_{name}", "name": name})
    for d in dining:
        name = (d.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            dinings.append({"id": d.get("id") or f"food_{name}", "name": name})
    return pois, dinings


def _index(points: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p.get("name", ""): p for p in points if p.get("name")}


def run_build_route(
    destination: str,
    days: int,
    itinerary_lines: list[dict[str, Any]] | None = None,
    loose_pois: list[dict[str, Any]] | None = None,
    dining_items: list[dict[str, Any]] | None = None,
    late_start: bool = False,
    extra_context: str = "",
) -> dict[str, Any]:
    try:
        _require({"destination": destination, "days": days}, ["destination", "days"], "build_route")
        lines = _normalize_itinerary_lines(list(itinerary_lines or []))
        loose = list(loose_pois or [])
        dining = list(dining_items or [])
        if not lines and not loose:
            return _fail(
                "需要 itinerary_lines 或 loose_pois（玩法检索未接入时可手写景点名列表）",
                "missing_params",
            )
        if lines and _line_stop_count(lines) == 0 and not loose:
            return _fail(
                "itinerary_lines 未识别到 stops（请用 stops:[{name,role}]，不要用 points）",
                "invalid_params",
            )
        warnings: list[str] = []
        if lines and _line_stop_count(lines) == 0 and loose:
            warnings.append(
                "itinerary_lines 无有效 stops，仅使用 loose_pois 补位；"
                "请改用 stops:[{name,role}] 而非 points"
            )
        days_n = max(int(days), 1)
        use_late = late_start or any(k in (extra_context or "") for k in ("不要早起", "不早起", "晚出发"))
        poi_names, dining_names = _collect_route_names(lines, loose, dining)
        geo_poi_list: list[dict] = []
        geo_dining_list: list[dict] = []
        if poi_names:
            g = run_geocode_places(destination, poi_names, "poi")
            if not g.get("ok"):
                return g
            geo_poi_list = g.get("places") or []
        if dining_names:
            g = run_geocode_places(destination, dining_names, "dining")
            if not g.get("ok"):
                return g
            geo_dining_list = g.get("places") or []
        geo_poi, geo_dining = _index(geo_poi_list), _index(geo_dining_list)
        by_heat = sorted(lines, key=lambda x: float(x.get("heat") or 0), reverse=True)
        queue = list(by_heat)
        used: set[str] = set()
        day_plans: list[dict] = []
        for day_i in range(1, days_n + 1):
            stops: list[dict] = []
            summary_parts: list[str] = []
            line_stop_count = 0
            if queue:
                ln = queue.pop(0)
                summary_parts.append(ln.get("title") or ln.get("id") or "线路")
                slots = ["am", "pm", "eve"]
                si = 0
                for st in ln.get("stops") or []:
                    name = (st.get("name") or "").strip()
                    if not name:
                        continue
                    role = st.get("role") or "poi"
                    if role != "food" and name in used:
                        continue
                    if role != "food":
                        used.add(name)
                    g = geo_dining.get(name) if role == "food" else geo_poi.get(name)
                    g = g or {}
                    slot = "lunch" if role == "food" else slots[min(si, len(slots) - 1)]
                    if role != "food":
                        si += 1
                        line_stop_count += 1
                    stops.append(
                        {
                            "id": str(g.get("id") or name),
                            "name": name,
                            "type": "dining" if role == "food" else "poi",
                            "slot": slot,
                            "lat": float(g.get("lat") or 0),
                            "lng": float(g.get("lng") or 0),
                            "duration_min": 60 if role == "food" else 120,
                            "reason": f"整线:{ln.get('id', '')}",
                        }
                    )
            # 散落补位：仅当当天已有整线点时追加到末尾；若整线为空才允许补位点单独成日
            allow_loose_only = line_stop_count == 0
            if line_stop_count > 0 or allow_loose_only:
                for p in loose:
                    name = (p.get("name") or "").strip()
                    if not name or name in used:
                        continue
                    used.add(name)
                    g = geo_poi.get(name) or {}
                    stops.append(
                        {
                            "id": str(g.get("id") or name),
                            "name": name,
                            "type": "poi",
                            "slot": "eve" if line_stop_count > 0 else "pm",
                            "lat": float(g.get("lat") or 0),
                            "lng": float(g.get("lng") or 0),
                            "duration_min": 90,
                            "reason": "散落补位",
                        }
                    )
                    summary_parts.append(f"+{name}")
                    break
            day_plans.append(
                {
                    "day": day_i,
                    "start_time": "10:00" if use_late else "09:30",
                    "stops": stops,
                    "summary": "；".join(summary_parts) or f"D{day_i}",
                }
            )
        unused = [str(ln.get("id") or "") for ln in queue if ln.get("id")]
        result = _ok(
            days=day_plans,
            geo_poi=geo_poi_list,
            geo_dining=geo_dining_list,
            unused_line_ids=unused,
            source="lines+geocode",
        )
        if warnings:
            result["warnings"] = warnings
        return result
    except ValueError as exc:
        return _fail(str(exc), "missing_params")
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))


def _day_anchors(daily_routes: dict[str, Any]) -> list[dict[str, Any]]:
    """每天优先取「整线」首个有坐标的 poi；没有整线点才回退到散落补位。"""
    anchors: list[dict[str, Any]] = []
    for day in daily_routes.get("days") or []:
        stops = list(day.get("stops") or [])
        chosen: dict[str, Any] | None = None
        for stop in stops:
            if stop.get("type") == "hotel":
                continue
            reason = str(stop.get("reason") or "")
            if reason.startswith("散落"):
                continue
            lat, lng = float(stop.get("lat") or 0), float(stop.get("lng") or 0)
            if lat or lng:
                chosen = stop
                break
        if chosen is None:
            for stop in stops:
                if stop.get("type") == "hotel":
                    continue
                lat, lng = float(stop.get("lat") or 0), float(stop.get("lng") or 0)
                if lat or lng:
                    chosen = stop
                    break
        if chosen is not None:
            anchors.append(
                {
                    "day": day.get("day"),
                    "name": chosen.get("name", ""),
                    "lat": float(chosen.get("lat") or 0),
                    "lng": float(chosen.get("lng") or 0),
                    "reason": chosen.get("reason") or "",
                }
            )
    return anchors


def run_search_stay(
    destination: str,
    check_in_date: str,
    stay_nights: int,
    daily_routes: dict[str, Any] | None = None,
    anchors: list[dict[str, Any]] | None = None,
    tier: str = "",
    extra_context: str = "",
) -> dict[str, Any]:
    try:
        _ = extra_context
        _require(
            {"destination": destination, "check_in_date": check_in_date, "stay_nights": stay_nights},
            ["destination", "check_in_date", "stay_nights"],
            "search_stay",
        )
        use_tier: HotelTier = (tier or DEFAULT_HOTEL_TIER)  # type: ignore[assignment]
        if use_tier not in ("luxury", "comfort", "economy"):
            use_tier = "comfort"
        anchor_list = list(anchors or [])
        if not anchor_list and daily_routes:
            anchor_list = _day_anchors(daily_routes)
        if not anchor_list:
            return _fail("需要 daily_routes 或 anchors", "missing_params")
        primary = anchor_list[0]
        area_name = f"近{primary.get('name') or '日行程起点'}"
        nights = max(int(stay_nights), 1)
        fallback_names = [str(a.get("name") or "") for a in anchor_list if a.get("name")]
        hotel: dict[str, Any] | None = None
        source = ""
        if DUTU_API_KEY:
            try:
                client = DidaHotelClient()
                star = TIER_STAR_INT[use_tier]
                origin = f"{destination}{TIER_KEYWORDS[use_tier]}"
                plans = [(area_name, "区/县"), (area_name, "景点"), (destination, "城市")]
                for n in fallback_names[:3]:
                    plans.append((n, "景点"))
                for place, place_type in plans:
                    if not place:
                        continue
                    hotels = client.search_hotels(
                        place=place,
                        place_type=place_type,
                        origin_query=origin,
                        check_in_date=check_in_date,
                        stay_nights=nights,
                        tier=use_tier,
                        size=3,
                    )
                    if not hotels:
                        continue
                    parsed = parse_hotel_fields(hotels[0])
                    price = parsed.get("price_per_night") or None
                    price_source = "dida" if price else "unavailable"
                    if parsed["hotel_id"]:
                        detail = client.get_hotel_detail(
                            parsed["hotel_id"],
                            check_in_date=check_in_date,
                            stay_nights=nights,
                        )
                        dp = parse_hotel_price(detail)
                        if dp:
                            price = dp
                            price_source = "dida+detail"
                    if not price:
                        price = None
                        if price_source == "dida":
                            price_source = "unavailable"
                    hotel = {
                        "tier": use_tier,
                        "name": parsed["name"] or f"{place}{TIER_KEYWORDS[use_tier]}",
                        "lat": parsed["lat"],
                        "lng": parsed["lng"],
                        "address": parsed["address"],
                        "area": area_name,
                        "price_per_night": price,
                        "star": parsed["star"] or star,
                        "dida_hotel_id": parsed["hotel_id"],
                        "price_source": price_source,
                    }
                    source = price_source
                    break
            except Exception as exc:  # noqa: BLE001
                logger.warning("道旅不可用，回退高德: %s", exc)
        if hotel is None:
            amap = AmapClient()
            lat0 = float(primary.get("lat") or 0)
            lng0 = float(primary.get("lng") or 0)
            # 锚点过偏/无结果时：放大半径，再退到城市中心搜一次
            attempts: list[tuple[float, float, int, str]] = [
                (lat0, lng0, STAY_HOTEL_SEARCH_RADIUS, area_name),
                (lat0, lng0, max(STAY_HOTEL_SEARCH_RADIUS * 3, 10000), area_name),
            ]
            city_geo = amap.geocode(destination, destination)
            if city_geo.get("ok"):
                attempts.append(
                    (
                        float(city_geo["lat"]),
                        float(city_geo["lng"]),
                        max(STAY_HOTEL_SEARCH_RADIUS * 2, 8000),
                        f"{destination}市区",
                    )
                )
            last_err = "未找到酒店"
            search: dict[str, Any] = {"ok": False}
            for alat, alng, radius, area_label in attempts:
                if not (alat or alng):
                    continue
                search = amap.search_hotels_near(
                    alat, alng, use_tier, destination, radius=radius
                )
                if search.get("ok"):
                    area_name = area_label
                    break
                last_err = str(search.get("error") or last_err)
            if not search.get("ok"):
                return _fail(last_err, "empty_result")
            h = search["hotel"]
            hotel = {
                "tier": use_tier,
                "name": h["name"],
                "lat": h["lat"],
                "lng": h["lng"],
                "address": h.get("address", ""),
                "area": area_name,
                "price_per_night": None,
                "amap_id": h.get("amap_id", ""),
                "star": TIER_STAR_INT[use_tier],
                "price_source": "unavailable",
            }
            source = "amap"
        return _ok(
            destination=destination,
            tier=use_tier,
            hotel=hotel,
            day_anchors=anchor_list,
            geo_hotels=[
                {
                    "id": f"hotel_{use_tier}",
                    "name": hotel["name"],
                    "lat": hotel["lat"],
                    "lng": hotel["lng"],
                    "category": "hotel",
                    "address": hotel.get("address", ""),
                }
            ],
            source=source,
        )
    except ValueError as exc:
        return _fail(str(exc), "missing_params")
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))


WALK_THRESHOLD_KM = 0.8
TIER_MODE: dict[HotelTier, str] = {"economy": "transit", "comfort": "transit", "luxury": "driving"}


def _estimate_segment(a: dict[str, Any], b: dict[str, Any], mode: str) -> dict[str, Any]:
    distance_km = point_dist_km(a, b)
    if mode == "walking" or distance_km <= WALK_THRESHOLD_KM:
        mode, speed, cost = "walking", 4.5, 0.0
    elif mode == "driving":
        speed, cost = 25.0, round(distance_km * 2.5, 1)
    else:
        mode, speed, cost = "transit", 18.0, 4.0
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


def _coerce_hotel(
    hotel: Any,
    daily_routes: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    """规范化 hotel；缺坐标时用行程整线首站顶上，避免向用户追问英文 hotel。"""
    warnings = ""
    if isinstance(hotel, str):
        name = hotel.strip()
        hotel = {"name": name} if name else {}
        if name:
            warnings = "hotel 为名称字符串，已尝试用行程首站坐标接驳"
    if not isinstance(hotel, dict):
        hotel = {}
    lat = float(hotel.get("lat") or 0)
    lng = float(hotel.get("lng") or 0)
    if lat or lng:
        return hotel, warnings
    for day in daily_routes.get("days") or []:
        if not isinstance(day, dict):
            continue
        for stop in day.get("stops") or []:
            if not isinstance(stop, dict):
                continue
            if stop.get("type") == "hotel":
                continue
            reason = str(stop.get("reason") or "")
            if reason.startswith("散落"):
                continue
            slat, slng = float(stop.get("lat") or 0), float(stop.get("lng") or 0)
            if not (slat or slng):
                continue
            fallback = {
                "id": stop.get("id") or "route_anchor",
                "name": hotel.get("name") or stop.get("name") or "行程锚点",
                "lat": slat,
                "lng": slng,
                "address": "",
                "area": f"近{stop.get('name') or '首站'}",
            }
            note = "hotel 缺坐标，已用每日整线首站作为接驳起点"
            return fallback, (warnings + "；" + note).strip("；") if warnings else note
    return None, warnings or "hotel 缺少 lat/lng，且行程中无可用锚点"


def run_plan_transport(
    origin: str,
    destination: str,
    daily_routes: dict[str, Any],
    hotel: Any = None,
    tier: str = "comfort",
    extra_context: str = "",
) -> dict[str, Any]:
    try:
        _ = extra_context
        if not isinstance(daily_routes, dict):
            return _fail("daily_routes 须为对象（含 days）", "invalid_params")
        _require(
            {"origin": origin, "destination": destination, "daily_routes": daily_routes},
            ["origin", "destination", "daily_routes"],
            "plan_transport",
        )
        days = daily_routes.get("days") or []
        if not days:
            return _fail("daily_routes.days 为空", "missing_params")
        hotel_obj, hotel_note = _coerce_hotel(hotel, daily_routes)
        if hotel_obj is None:
            return _fail(
                hotel_note or "缺少酒店坐标；请先成功调用 search_stay 或传入带 lat/lng 的 hotel",
                "upstream_gap",
            )
        use_tier: HotelTier = (tier or "comfort")  # type: ignore[assignment]
        if use_tier not in ("luxury", "comfort", "economy"):
            use_tier = "comfort"
        client: AmapClient | None = None
        try:
            client = AmapClient()
        except Exception:
            client = None
        hotel_pt = {
            "id": hotel_obj.get("id") or "hotel",
            "name": hotel_obj.get("name") or "酒店",
            "lat": float(hotel_obj.get("lat") or 0),
            "lng": float(hotel_obj.get("lng") or 0),
        }
        segments: list[dict] = []
        daily_summaries: list[str] = []
        for day in days:
            if not isinstance(day, dict):
                continue
            stops = day.get("stops") or []
            prev = hotel_pt
            parts: list[str] = []
            for stop in stops:
                if not isinstance(stop, dict):
                    continue
                stop_pt = {
                    "id": stop.get("id", ""),
                    "name": stop.get("name", ""),
                    "lat": float(stop.get("lat") or 0),
                    "lng": float(stop.get("lng") or 0),
                }
                if not (stop_pt["lat"] or stop_pt["lng"]):
                    continue
                preferred = TIER_MODE.get(use_tier, "transit")
                if point_dist_km(prev, stop_pt) <= WALK_THRESHOLD_KM:
                    preferred = "walking"
                result: dict[str, Any] = {"ok": False}
                if client:
                    if preferred == "walking":
                        result = client.direction_walking(prev, stop_pt)
                    elif preferred == "driving":
                        result = client.direction_driving(prev, stop_pt)
                    else:
                        result = client.direction_transit(prev, stop_pt, destination)
                if not result.get("ok"):
                    result = _estimate_segment(prev, stop_pt, preferred)
                segments.append(
                    {
                        "from_name": str(prev.get("name") or ""),
                        "to_name": str(stop_pt.get("name") or ""),
                        "mode": result.get("mode", preferred),
                        "duration_min": int(result.get("duration_min", 0)),
                        "distance_km": float(result.get("distance_km", 0)),
                        "cost_estimate": float(result.get("cost_estimate", 0)),
                        "summary": str(result.get("summary", "")),
                        "source": str(result.get("source", "amap")),
                    }
                )
                parts.append(f"{prev.get('name')}→{stop_pt.get('name')} {result.get('summary')}")
                prev = stop_pt
            daily_summaries.append(f"D{day.get('day', 0)}: " + ("；".join(parts[:3]) if parts else "无行程"))
        out = _ok(
            intercity={
                "mode": "高铁/航班待确认",
                "summary": f"{origin} → {destination}",
                "note": "大交通未接入",
                "source": "placeholder",
            },
            segments=segments,
            daily_summaries=daily_summaries,
            total_commute_min=sum(s["duration_min"] for s in segments),
            total_cost_estimate=round(sum(s["cost_estimate"] for s in segments), 1),
            hotel_used=hotel_pt,
            source="amap" if client else "estimate",
        )
        if hotel_note:
            out["warnings"] = [hotel_note]
        return out
    except ValueError as exc:
        return _fail(str(exc), "missing_params")
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))
