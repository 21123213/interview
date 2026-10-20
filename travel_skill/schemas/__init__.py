"""入参 / 出参模型（均含中文 Field 注释）。"""

from travel_skill.schemas.common import ToolEnvelope
from travel_skill.schemas.culture import CultureInput, CultureToolResult
from travel_skill.schemas.geocode import GeocodeInput, GeocodeToolResult
from travel_skill.schemas.route import RouteInput, RouteToolResult
from travel_skill.schemas.stay import StayInput, StayToolResult
from travel_skill.schemas.transport import TransportInput, TransportToolResult
from travel_skill.schemas.weather import WeatherInput, WeatherToolResult

__all__ = [
    "ToolEnvelope",
    "WeatherInput",
    "WeatherToolResult",
    "CultureInput",
    "CultureToolResult",
    "GeocodeInput",
    "GeocodeToolResult",
    "RouteInput",
    "RouteToolResult",
    "StayInput",
    "StayToolResult",
    "TransportInput",
    "TransportToolResult",
]
