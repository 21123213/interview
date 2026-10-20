"""对外工具入口。"""

from travel_skill.tools.culture import get_culture
from travel_skill.tools.geocode import geocode_places
from travel_skill.tools.route import build_route
from travel_skill.tools.stay import search_stay
from travel_skill.tools.transport import plan_transport
from travel_skill.tools.weather import get_weather

TOOLS = [
    get_weather,
    get_culture,
    geocode_places,
    build_route,
    search_stay,
    plan_transport,
]

__all__ = [
    "TOOLS",
    "get_weather",
    "get_culture",
    "geocode_places",
    "build_route",
    "search_stay",
    "plan_transport",
]
