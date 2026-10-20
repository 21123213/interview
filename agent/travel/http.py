"""旅游相关 HTTP 薄封装。"""

from __future__ import annotations

from typing import Any

import requests


def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return {"ok": True, "data": resp.json(), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "data": None, "error": str(exc)}


def http_post(
    url: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    try:
        resp = requests.post(url, json=json, headers=headers, timeout=timeout)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        return {"ok": True, "data": data, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "data": None, "error": str(exc)}
