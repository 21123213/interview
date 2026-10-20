"""?????"""

from __future__ import annotations

import math
from typing import Any, TypeVar

T = TypeVar("T")


def dist_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    if not a_lat or not a_lng or not b_lat or not b_lng:
        return 9999.0
    r = 6371.0
    d_lat = math.radians(b_lat - a_lat)
    d_lng = math.radians(b_lng - a_lng)
    x = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(x))


def point_dist_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    return dist_km(
        float(a.get("lat", 0)),
        float(a.get("lng", 0)),
        float(b.get("lat", 0)),
        float(b.get("lng", 0)),
    )
