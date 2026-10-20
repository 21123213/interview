"""旅游工具环境变量（与 travel_skill 命名一致，读仓库根 .env）。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

QWEATHER_KEY = os.getenv("QWEATHER_KEY", "").strip()
QWEATHER_HOST = os.getenv("QWEATHER_HOST", "").strip().rstrip("/")

BOCHA_API_KEY = os.getenv("BOCHA_API_KEY", "").strip()
BOCHA_API_BASE = os.getenv("BOCHA_API_BASE", "https://api.bochaai.com").strip().rstrip("/")

AMAP_KEY = os.getenv("AMAP_KEY", "").strip()
AMAP_API_BASE = os.getenv("AMAP_API_BASE", "https://restapi.amap.com").strip().rstrip("/")
STAY_HOTEL_SEARCH_RADIUS = int(os.getenv("STAY_HOTEL_SEARCH_RADIUS", "3000"))

DUTU_API_KEY = os.getenv("DUTU_API_KEY", "").strip()
DIDA_MCP_URL = os.getenv("DIDA_MCP_URL", "https://mcp.rollinggo.cn/mcp").strip().rstrip("/")
DEFAULT_HOTEL_TIER = os.getenv("DEFAULT_HOTEL_TIER", "comfort").strip() or "comfort"

# 小红书 xhs_search（xiaohongshu-skills Bridge）
XHS_SKILLS_ROOT = os.getenv(
    "XHS_SKILLS_ROOT",
    str(ROOT / "xiaohongshu-skills-main"),
).strip()

HTTP_TIMEOUT = float(os.getenv("TRAVEL_HTTP_TIMEOUT", "20"))
