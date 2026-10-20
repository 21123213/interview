"""小红书检索（xiaohongshu-skills Bridge，同进程调用）。

供 agent `xhs_search`：search_feeds → get_feed_detail → 正文长度过滤。
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from travel_skill.logging_utils import get_logger
from travel_skill.shared.config import XHS_NOTE_MIN_CHARS, XHS_SKILLS_ROOT

logger = get_logger("travel_skill.xhs")

BRIDGE_URL = "ws://localhost:9333"
_SKIP_MODEL_TYPES = frozenset({"hot_query"})


def _ensure_skills_on_path() -> Path:
    root = XHS_SKILLS_ROOT
    if not root.is_dir():
        raise FileNotFoundError(f"小红书 skills 目录不存在: {root}")
    scripts = root / "scripts"
    scripts_str = str(scripts)
    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)
    return root


def _ensure_bridge_ready(bridge_url: str = BRIDGE_URL) -> None:
    """确保 bridge_server 运行且扩展已连接（逻辑对齐 skills CLI）。"""
    from xhs.bridge import BridgePage

    page = BridgePage(bridge_url)
    if not page.is_server_running():
        logger.info("Bridge server 未运行，正在启动...")
        scripts_dir = _ensure_skills_on_path() / "scripts"
        kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [sys.executable, str(scripts_dir / "bridge_server.py")],
            **kwargs,
        )
        for _ in range(15):
            time.sleep(1)
            if page.is_server_running():
                break
        else:
            raise RuntimeError("Bridge server 启动超时，请手动运行 bridge_server.py")

    if page.is_extension_connected():
        return

    logger.warning("浏览器扩展未连接：请打开 Chrome、启用 XHS Bridge，并登录小红书")
    for _ in range(20):
        time.sleep(1)
        if page.is_extension_connected():
            return
    raise RuntimeError("XHS Bridge 扩展未连接（chrome://extensions 确认已启用）")


class _XhsBridgeSession:
    """同进程复用 BridgePage，避免每次 uv run 冷启。"""

    def __init__(self, bridge_url: str = BRIDGE_URL) -> None:
        self._bridge_url = bridge_url
        self._page = None
        self._lock = threading.Lock()
        self._ready = False

    def _ensure(self) -> Any:
        _ensure_skills_on_path()
        if self._ready and self._page is not None:
            return self._page
        _ensure_bridge_ready(self._bridge_url)
        from xhs.bridge import BridgePage

        self._page = BridgePage(self._bridge_url)
        self._ready = True
        return self._page

    def search_feeds(self, keyword: str) -> list[dict[str, Any]]:
        with self._lock:
            page = self._ensure()
            from xhs.search import search_feeds as _search

            feeds = _search(page, keyword)
            return [f.to_dict() for f in feeds]

    def get_feed_detail(
        self,
        feed_id: str,
        xsec_token: str,
        *,
        keyword: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            page = self._ensure()
            from xhs.feed_detail import get_feed_detail as _detail
            from xhs.types import CommentLoadConfig

            config = CommentLoadConfig(max_comment_items=0)
            detail = _detail(
                page,
                feed_id,
                xsec_token,
                load_all_comments=False,
                config=config,
                keyword=keyword or "旅游",
            )
            return detail.to_dict()


_session: _XhsBridgeSession | None = None
_session_lock = threading.Lock()


def get_bridge_session() -> _XhsBridgeSession:
    global _session
    with _session_lock:
        if _session is None:
            _session = _XhsBridgeSession()
        return _session


def normalize_feeds(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """去掉热搜卡片、缺 id/token 的项。"""
    out: list[dict[str, Any]] = []
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        if feed.get("modelType") in _SKIP_MODEL_TYPES:
            continue
        feed_id = str(feed.get("id") or "").strip()
        token = str(feed.get("xsecToken") or "").strip()
        if not feed_id or not token or "#" in feed_id:
            continue
        out.append(feed)
    return out


def search_feeds(keyword: str) -> dict[str, Any]:
    feeds = normalize_feeds(get_bridge_session().search_feeds(keyword))
    logger.info("search_feeds keyword=%s count=%s", keyword, len(feeds))
    return {"feeds": feeds, "count": len(feeds)}


def get_feed_detail(feed_id: str, xsec_token: str, *, keyword: str = "") -> dict[str, Any]:
    return get_bridge_session().get_feed_detail(feed_id, xsec_token, keyword=keyword)


def note_text_content(note: dict[str, Any]) -> str:
    body = str(note.get("body") or "").strip()
    if body:
        return body
    return str(note.get("desc") or "").strip()


def is_note_usable(note: dict[str, Any], *, min_chars: int = XHS_NOTE_MIN_CHARS) -> bool:
    """正文超过 min_chars 才保留（默认 >50，即不超过 50 字的不用）。"""
    return len(note_text_content(note)) > min_chars
