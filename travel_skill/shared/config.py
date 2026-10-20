"""环境变量与密钥（无 mock 模式）。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


QWEATHER_KEY = os.getenv("QWEATHER_KEY", "").strip()
QWEATHER_HOST = os.getenv("QWEATHER_HOST", "").strip().rstrip("/")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
# 与主 Agent 一致：OpenAI 兼容接口 + qwen3.8 系列（见 shared/llm_client.py）
MODEL_NAME = os.getenv("TRAVEL_MODEL_NAME") or os.getenv(
    "DASHSCOPE_STRONG_MODEL", "qwen3.8-max"
)
MODEL_FALLBACK = (
    os.getenv("TRAVEL_MODEL_FALLBACK")
    or os.getenv("DASHSCOPE_FAST_MODEL")
    or "qwen3.8-flash"
).strip()

LLM_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT_SEC", "90"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "2"))
HTTP_BACKOFF_BASE_SEC = float(os.getenv("HTTP_BACKOFF_BASE_SEC", "0.5"))

LANGSMITH_TRACING = env_bool("LANGSMITH_TRACING", default=False) or env_bool(
    "LANGCHAIN_TRACING_V2", default=False
)
# travel_skill 成本日志：默认写到 agent/logs/travel_skill/metrics.jsonl
# 看字段 kind / purpose / tokens_in / tokens_out / latency_ms / status
# 设 OBS_METRICS_JSONL=0 或 off 可关闭；也可改成自定义路径
_obs_raw = os.getenv("OBS_METRICS_JSONL")
if _obs_raw is None:
    OBS_METRICS_JSONL = str(
        PROJECT_ROOT / "agent" / "logs" / "travel_skill" / "metrics.jsonl"
    )
else:
    OBS_METRICS_JSONL = _obs_raw.strip()
    if OBS_METRICS_JSONL.lower() in {"0", "false", "off", "none", ""}:
        OBS_METRICS_JSONL = ""
OBS_PRINT_SUMMARY = env_bool("OBS_PRINT_SUMMARY", default=True)

BOCHA_API_KEY = os.getenv("BOCHA_API_KEY", "").strip()
BOCHA_API_BASE = os.getenv("BOCHA_API_BASE", "https://api.bochaai.com").strip().rstrip("/")

XHS_SKILLS_ROOT = Path(
    os.getenv("XHS_SKILLS_ROOT", str(PROJECT_ROOT / "xiaohongshu-skills-main"))
).resolve()
# 正文长度阈值：不超过该字数的笔记丢弃（默认 50 → 须 >50 字才保留）
XHS_NOTE_MIN_CHARS = int(
    os.getenv("XHS_NOTE_MIN_CHARS") or os.getenv("PLAY_NOTE_MIN_CHARS") or "50"
)

AMAP_KEY = os.getenv("AMAP_KEY", "").strip()
AMAP_API_BASE = os.getenv("AMAP_API_BASE", "https://restapi.amap.com").strip().rstrip("/")
STAY_HOTEL_SEARCH_RADIUS = int(os.getenv("STAY_HOTEL_SEARCH_RADIUS", "3000"))

DUTU_API_KEY = os.getenv("DUTU_API_KEY", "").strip()
DIDA_MCP_URL = os.getenv("DIDA_MCP_URL", "https://mcp.rollinggo.cn/mcp").strip().rstrip("/")

# 住宿未指定档位时的静默默认（不向调用方追问）
DEFAULT_HOTEL_TIER = os.getenv("DEFAULT_HOTEL_TIER", "comfort").strip() or "comfort"
