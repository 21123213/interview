"""和风天气客户端。"""

from __future__ import annotations

from typing import Any

from travel_skill.logging_utils import get_logger
from travel_skill.shared.config import QWEATHER_HOST, QWEATHER_KEY
from travel_skill.shared.http_client import http_get

logger = get_logger("travel_skill.qweather")

LANG = "zh"
UNIT = "m"
REQUEST_TIMEOUT = 10


class QWeatherClient:
    def __init__(self, key: str | None = None, host: str | None = None):
        self.key = key or QWEATHER_KEY
        self.host = (host or QWEATHER_HOST).rstrip("/")
        if not self.key:
            raise RuntimeError("未配置 QWEATHER_KEY")
        if not self.host:
            raise RuntimeError("未配置 QWEATHER_HOST")

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.host}{endpoint}"
        base_params = {"key": self.key, "lang": LANG, "unit": UNIT}
        base_params.update(params)
        wrapped = http_get(
            url,
            params=base_params,
            purpose=f"weather{endpoint}",
            provider="qweather",
            timeout=REQUEST_TIMEOUT,
        )
        if not wrapped.get("ok"):
            return {"ok": False, "error": wrapped.get("error") or "网络请求异常", "data": None}
        data = wrapped.get("data") or {}
        if data.get("code") != "200":
            return {
                "ok": False,
                "error": f"接口错误 code={data.get('code')}, msg={data.get('message', '')}",
                "data": data,
            }
        return {"ok": True, "error": None, "data": data}

    def search_city(self, city_name: str) -> dict[str, Any]:
        return self._request("/geo/v2/city/lookup", {"location": city_name})

    def get_daily_forecast(self, location: str) -> dict[str, Any]:
        return self._request("/v7/weather/30d", {"location": location})


def fetch_weather_bundle(city_name: str) -> dict[str, Any]:
    client = QWeatherClient()
    logger.info("查询城市: %s", city_name)
    city_result = client.search_city(city_name)
    if not city_result["ok"]:
        return {"ok": False, "error": city_result["error"]}

    locations = city_result["data"].get("location") or []
    if not locations:
        return {"ok": False, "error": f"未找到城市: {city_name}"}

    location = locations[0]
    location_id = location["id"]
    daily_result = client.get_daily_forecast(location_id)
    if not daily_result["ok"]:
        return {"ok": False, "error": daily_result["error"], "location": location}

    return {
        "ok": True,
        "error": None,
        "location": location,
        "daily_forecast": daily_result,
    }
