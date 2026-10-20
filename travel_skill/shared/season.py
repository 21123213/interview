"""行程季节推断与文案（供 get_culture 等使用）。"""

from __future__ import annotations

_SEASON_ALIASES = {
    "春": "春",
    "夏": "夏",
    "秋": "秋",
    "冬": "冬",
    "spring": "春",
    "summer": "夏",
    "autumn": "秋",
    "fall": "秋",
    "winter": "冬",
}

_MONTH_SEASON = {
    1: "冬",
    2: "冬",
    3: "春",
    4: "春",
    5: "春",
    6: "夏",
    7: "夏",
    8: "夏",
    9: "秋",
    10: "秋",
    11: "秋",
    12: "冬",
}


def normalize_season(season: str | None, start_date: str = "") -> str:
    """返回 春/夏/秋/冬；优先显式 season，否则由 start_date 月份推断。"""
    raw = (season or "").strip().lower()
    for key, val in _SEASON_ALIASES.items():
        if key in raw:
            return val
    if start_date and len(start_date) >= 7:
        try:
            month = int(start_date[5:7])
            return _MONTH_SEASON.get(month, "")
        except ValueError:
            pass
    return ""


def season_label(season: str) -> str:
    mapping = {"春": "春季", "夏": "夏季", "秋": "秋季", "冬": "冬季"}
    return mapping.get(season, season or "出行当期")
