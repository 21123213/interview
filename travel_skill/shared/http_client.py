"""?? HTTP?timeout + ?? + ???"""

from __future__ import annotations

import time
from typing import Any

import requests

from travel_skill.logging_utils import get_logger
from travel_skill.shared import observability as obs
from travel_skill.shared.config import HTTP_BACKOFF_BASE_SEC, HTTP_MAX_RETRIES
from travel_skill.shared.resilience import call_with_retry, is_retryable_error

logger = get_logger("travel_skill.http_client")


def _retryable_http(exc: BaseException) -> bool:
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        return code == 429 or code >= 500
    return is_retryable_error(exc)


def http_request(
    method: str,
    url: str,
    *,
    purpose: str,
    provider: str,
    timeout: float = 15.0,
    max_retries: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    attempts = max(1, HTTP_MAX_RETRIES if max_retries is None else max_retries)
    retries_used = 0
    t0 = time.perf_counter()
    status_code: int | None = None

    def _do() -> requests.Response:
        nonlocal status_code
        resp = requests.request(method.upper(), url, timeout=timeout, **kwargs)
        status_code = resp.status_code
        if resp.status_code == 429 or resp.status_code >= 500:
            resp.raise_for_status()
        return resp

    def _on_retry(n: int, exc: BaseException, delay: float) -> None:
        nonlocal retries_used
        retries_used += 1
        logger.warning(
            "HTTP retry purpose=%s provider=%s attempt=%d delay=%.2fs err=%s",
            purpose,
            provider,
            n,
            delay,
            exc,
        )

    try:
        resp = call_with_retry(
            _do,
            max_attempts=attempts,
            backoff_base=HTTP_BACKOFF_BASE_SEC,
            retry_on=_retryable_http,
            on_retry=_on_retry,
        )
        if resp.status_code >= 400:
            latency_ms = (time.perf_counter() - t0) * 1000
            err = f"HTTP {resp.status_code}"
            obs.record_call(
                kind="http",
                purpose=purpose,
                status="error",
                latency_ms=latency_ms,
                provider=provider,
                retries=retries_used,
                error=err,
                extra={"status_code": resp.status_code, "url": url},
            )
            return {
                "ok": False,
                "data": None,
                "error": err,
                "latency_ms": round(latency_ms, 1),
                "retries": retries_used,
                "provider": provider,
                "purpose": purpose,
                "status_code": resp.status_code,
            }

        try:
            data: Any = resp.json()
        except ValueError:
            data = {"text": resp.text}

        latency_ms = (time.perf_counter() - t0) * 1000
        obs.record_call(
            kind="http",
            purpose=purpose,
            status="success",
            latency_ms=latency_ms,
            provider=provider,
            retries=retries_used,
            extra={"status_code": resp.status_code},
        )
        return {
            "ok": True,
            "data": data,
            "error": None,
            "latency_ms": round(latency_ms, 1),
            "retries": retries_used,
            "provider": provider,
            "purpose": purpose,
            "status_code": resp.status_code,
        }
    except BaseException as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        obs.record_call(
            kind="http",
            purpose=purpose,
            status="error",
            latency_ms=latency_ms,
            provider=provider,
            retries=retries_used,
            error=str(exc),
        )
        return {
            "ok": False,
            "data": None,
            "error": str(exc),
            "latency_ms": round(latency_ms, 1),
            "retries": retries_used,
            "provider": provider,
            "purpose": purpose,
            "status_code": status_code,
        }


def http_get(url: str, *, purpose: str, provider: str, timeout: float = 15.0, **kwargs: Any) -> dict[str, Any]:
    return http_request("GET", url, purpose=purpose, provider=provider, timeout=timeout, **kwargs)


def http_post(url: str, *, purpose: str, provider: str, timeout: float = 15.0, **kwargs: Any) -> dict[str, Any]:
    return http_request("POST", url, purpose=purpose, provider=provider, timeout=timeout, **kwargs)
