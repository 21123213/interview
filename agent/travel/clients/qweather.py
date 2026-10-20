"""和风天气。"""

from __future__ import annotations

import logging
from typing import Any

from agent.travel.config import QWEATHER_HOST, QWEATHER_KEY
from agent.travel.http import http_get

logger = logging.getLogger("agent.travel.qweather")


def fetch_weather_bundle(city_name: str) -> dict[str, Any]:
    if not QWEATHER_KEY or not QWEATHER_HOST:
        return {"ok": False, "error": "未配置 QWEATHER_KEY / QWEATHER_HOST"}

    base = QWEATHER_HOST.rstrip("/")
    common = {"key": QWEATHER_KEY, "lang": "zh", "unit": "m"}

    city = http_get(
        f"{base}/geo/v2/city/lookup",
        params={**common, "location": city_name},
        timeout=10,
    )
    if not city.get("ok"):
        return {"ok": False, "error": city.get("error") or "城市查询失败"}
    data = city.get("data") or {}
    if data.get("code") != "200":
        return {"ok": False, "error": f"和风 code={data.get('code')}"}
    locations = data.get("location") or []
    if not locations:
        return {"ok": False, "error": f"未找到城市: {city_name}"}
    location = locations[0]
    loc_id = location["id"]

    daily = http_get(
        f"{base}/v7/weather/30d",
        params={**common, "location": loc_id},
        timeout=10,
    )
    if not daily.get("ok"):
        return {"ok": False, "error": daily.get("error"), "location": location}
    ddata = daily.get("data") or {}
    if ddata.get("code") != "200":
        return {"ok": False, "error": f"预报 code={ddata.get('code')}", "location": location}

    logger.info("qweather city=%s id=%s", city_name, loc_id)
    return {
        "ok": True,
        "location": location,
        "daily_forecast": {"data": ddata},
    }
