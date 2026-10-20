"""工具内 LLM：走 DashScope OpenAI 兼容接口（与主 Agent 同路线）。"""

from __future__ import annotations

import os
import time
from typing import Any, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from openai import OpenAI

from travel_skill.logging_utils import get_logger
from travel_skill.shared import observability as obs
from travel_skill.shared.config import (
    DASHSCOPE_API_KEY,
    LLM_MAX_RETRIES,
    LLM_TIMEOUT_SEC,
    MODEL_FALLBACK,
    MODEL_NAME,
)
from travel_skill.shared.resilience import call_with_retry, is_retryable_error

logger = get_logger("travel_skill.llm_client")

DEFAULT_COMPAT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _compat_base_url() -> str:
    return (
        os.getenv("DASHSCOPE_COMPAT_BASE_URL")
        or os.getenv("TRAVEL_LLM_BASE_URL")
        or DEFAULT_COMPAT_BASE_URL
    ).rstrip("/")


def _client() -> OpenAI:
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("未设置 DASHSCOPE_API_KEY")
    return OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url=_compat_base_url(),
        timeout=LLM_TIMEOUT_SEC,
    )


def _messages_to_openai(messages: Sequence[BaseMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        content = m.content if isinstance(m.content, str) else str(m.content)
        if isinstance(m, SystemMessage):
            out.append({"role": "system", "content": content})
        elif isinstance(m, HumanMessage):
            out.append({"role": "user", "content": content})
        elif isinstance(m, AIMessage):
            out.append({"role": "assistant", "content": content})
        else:
            role = getattr(m, "type", None) or getattr(m, "role", "user")
            if role in {"system", "human", "user", "ai", "assistant"}:
                mapped = {
                    "system": "system",
                    "human": "user",
                    "user": "user",
                    "ai": "assistant",
                    "assistant": "assistant",
                }[role]
                out.append({"role": mapped, "content": content})
            else:
                out.append({"role": "user", "content": content})
    return out


def _invoke_once(model_name: str, messages: Sequence[BaseMessage], temperature: float) -> AIMessage:
    resp = _client().chat.completions.create(
        model=model_name,
        messages=_messages_to_openai(messages),
        temperature=temperature,
    )
    choice = resp.choices[0].message
    text = (choice.content or "").strip()
    usage = getattr(resp, "usage", None)
    meta = {
        "model_name": model_name,
        "token_usage": {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        },
    }
    return AIMessage(content=text, response_metadata=meta)


def _extract_tokens(response: Any) -> tuple[int, int]:
    meta = getattr(response, "usage_metadata", None) or {}
    if isinstance(meta, dict) and (meta.get("input_tokens") or meta.get("output_tokens")):
        return int(meta.get("input_tokens") or 0), int(meta.get("output_tokens") or 0)
    rm = getattr(response, "response_metadata", None) or {}
    if isinstance(rm, dict):
        usage = rm.get("token_usage") or rm.get("usage") or {}
        if isinstance(usage, dict):
            tin = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            tout = usage.get("output_tokens") or usage.get("completion_tokens") or 0
            return int(tin or 0), int(tout or 0)
    return 0, 0


def invoke_llm(
    messages: Sequence[BaseMessage],
    *,
    purpose: str,
    temperature: float = 0.2,
    allow_model_fallback: bool = True,
) -> Any:
    primary = MODEL_NAME
    fallback = (
        MODEL_FALLBACK
        if allow_model_fallback and MODEL_FALLBACK and MODEL_FALLBACK != primary
        else ""
    )
    attempts = max(1, LLM_MAX_RETRIES)
    last_exc: BaseException | None = None
    retries_used = 0

    def _try_model(name: str, is_fallback: bool) -> Any:
        nonlocal retries_used, last_exc
        t0 = time.perf_counter()
        try:

            def _do():
                return _invoke_once(name, messages, temperature)

            def _on_retry(n: int, exc: BaseException, delay: float) -> None:
                nonlocal retries_used
                retries_used += 1
                logger.warning(
                    "LLM retry purpose=%s model=%s attempt=%d delay=%.2fs err=%s",
                    purpose,
                    name,
                    n,
                    delay,
                    exc,
                )

            response = call_with_retry(
                _do,
                max_attempts=attempts,
                backoff_base=0.8,
                retry_on=is_retryable_error,
                on_retry=_on_retry,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            tin, tout = _extract_tokens(response)
            obs.record_call(
                kind="llm",
                purpose=purpose,
                status="fallback" if is_fallback else "success",
                latency_ms=latency_ms,
                provider="dashscope",
                model=name,
                tokens_in=tin,
                tokens_out=tout,
                retries=retries_used,
            )
            return response
        except BaseException as exc:
            last_exc = exc
            latency_ms = (time.perf_counter() - t0) * 1000
            if is_fallback or not fallback:
                obs.record_call(
                    kind="llm",
                    purpose=purpose,
                    status="error",
                    latency_ms=latency_ms,
                    provider="dashscope",
                    model=name,
                    retries=retries_used,
                    error=str(exc),
                )
            raise

    try:
        return _try_model(primary, is_fallback=False)
    except BaseException:
        if not fallback:
            raise
        return _try_model(fallback, is_fallback=True)
