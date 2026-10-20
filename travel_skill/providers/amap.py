"""高德地图：geocode / 周边酒店 / 路径规划。"""

from __future__ import annotations

from typing import Any

from travel_skill.logging_utils import get_logger
from travel_skill.schemas.stay import HotelTier
from travel_skill.shared.config import AMAP_API_BASE, AMAP_KEY, STAY_HOTEL_SEARCH_RADIUS
from travel_skill.shared.http_client import http_get

logger = get_logger("travel_skill.amap")
REQUEST_TIMEOUT = 15

TIER_KEYWORDS: dict[HotelTier, str] = {
    "luxury": "五星级酒店",
    "comfort": "精品酒店",
    "economy": "经济型酒店",
}


class AmapClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or AMAP_KEY
        self.base_url = (base_url or AMAP_API_BASE).rstrip("/")
        if not self.api_key:
            raise RuntimeError("未配置 AMAP_KEY")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = {**params, "key": self.api_key}
        wrapped = http_get(
            url,
            params=params,
            purpose=f"amap{path}",
            provider="amap",
            timeout=REQUEST_TIMEOUT,
        )
        if not wrapped.get("ok"):
            return {"status": "0", "info": wrapped.get("error") or "request failed"}
        data = wrapped.get("data")
        return data if isinstance(data, dict) else {"status": "0", "info": "invalid json"}

    def geocode(self, address: str, city: str) -> dict[str, Any]:
        body = self._get("/v3/geocode/geo", {"address": address, "city": city})
        if body.get("status") != "1" or not body.get("geocodes"):
            return {"ok": False, "error": body.get("info", "geocode 失败"), "lat": 0, "lng": 0}
        geo = body["geocodes"][0]
        location = geo.get("location", "")
        if not location or "," not in location:
            return {"ok": False, "error": "无坐标", "lat": 0, "lng": 0}
        lng_str, lat_str = location.split(",", 1)
        return {
            "ok": True,
            "lat": float(lat_str),
            "lng": float(lng_str),
            "address": geo.get("formatted_address", address),
        }

    def search_hotels_near(
        self,
        lat: float,
        lng: float,
        tier: HotelTier,
        city: str,
        radius: int = STAY_HOTEL_SEARCH_RADIUS,
    ) -> dict[str, Any]:
        body = self._get(
            "/v3/place/around",
            {
                "location": f"{lng},{lat}",
                "keywords": TIER_KEYWORDS[tier],
                "radius": radius,
                "city": city,
                "types": "100100",
                "offset": 5,
            },
        )
        pois = body.get("pois") or []
        if body.get("status") != "1" or not pois:
            return {"ok": False, "error": body.get("info", "未找到酒店"), "hotel": None}
        poi = pois[0]
        loc = poi.get("location", "")
        if "," not in loc:
            return {"ok": False, "error": "酒店无坐标", "hotel": None}
        lng_h, lat_h = loc.split(",", 1)
        return {
            "ok": True,
            "hotel": {
                "name": poi.get("name", ""),
                "lat": float(lat_h),
                "lng": float(lng_h),
                "address": poi.get("address", "") or poi.get("name", ""),
                "amap_id": poi.get("id", ""),
            },
        }

    def _origin_dest(self, from_pt: dict[str, Any], to_pt: dict[str, Any]) -> tuple[str, str]:
        return (
            f"{from_pt.get('lng', 0)},{from_pt.get('lat', 0)}",
            f"{to_pt.get('lng', 0)},{to_pt.get('lat', 0)}",
        )

    def direction_walking(self, from_pt: dict[str, Any], to_pt: dict[str, Any]) -> dict[str, Any]:
        origin, destination = self._origin_dest(from_pt, to_pt)
        body = self._get("/v3/direction/walking", {"origin": origin, "destination": destination})
        return self._parse_path(body, mode="walking")

    def direction_driving(self, from_pt: dict[str, Any], to_pt: dict[str, Any]) -> dict[str, Any]:
        origin, destination = self._origin_dest(from_pt, to_pt)
        body = self._get("/v3/direction/driving", {"origin": origin, "destination": destination})
        return self._parse_path(body, mode="driving")

    def direction_transit(
        self,
        from_pt: dict[str, Any],
        to_pt: dict[str, Any],
        city: str,
        strategy: int = 0,
    ) -> dict[str, Any]:
        origin, destination = self._origin_dest(from_pt, to_pt)
        body = self._get(
            "/v3/direction/transit/integrated",
            {
                "origin": origin,
                "destination": destination,
                "city": city,
                "cityd": city,
                "strategy": strategy,
            },
        )
        return self._parse_transit(body)

    def _parse_path(self, body: dict[str, Any], *, mode: str) -> dict[str, Any]:
        if body.get("status") != "1":
            return {"ok": False, "error": body.get("info", "路径失败")}
        route = (body.get("route") or {}).get("paths") or []
        if not route:
            return {"ok": False, "error": "无路径"}
        path = route[0]
        distance_km = float(path.get("distance", 0)) / 1000.0
        duration_min = max(1, int(int(path.get("duration", 0)) / 60))
        cost = round(distance_km * 2.5, 1) if mode == "driving" else 0.0
        label = "步行" if mode == "walking" else "驾车/打车"
        return {
            "ok": True,
            "mode": mode,
            "duration_min": duration_min,
            "distance_km": round(distance_km, 2),
            "summary": f"{label}约 {duration_min} 分钟",
            "cost_estimate": cost,
        }

    def _parse_transit(self, body: dict[str, Any]) -> dict[str, Any]:
        if body.get("status") != "1":
            return {"ok": False, "error": body.get("info", "公交路径失败")}
        transits = (body.get("route") or {}).get("transits") or []
        if not transits:
            return {"ok": False, "error": "无公交方案"}
        t0 = transits[0]
        duration_min = max(1, int(int(t0.get("duration", 0)) / 60))
        distance_km = float(t0.get("distance", 0)) / 1000.0
        return {
            "ok": True,
            "mode": "transit",
            "duration_min": duration_min,
            "distance_km": round(distance_km, 2),
            "summary": f"公交/地铁约 {duration_min} 分钟",
            "cost_estimate": 4.0,
        }
