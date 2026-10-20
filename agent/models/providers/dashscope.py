"""DashScope OpenAI 兼容模式 Provider。"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

from openai import OpenAI

from agent.models.base import ChatMessage, ChatModel, ModelResult, ToolCallRequest
from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer

logger = logging.getLogger("agent.models.dashscope")

DEFAULT_BASE_URL = "https://token-plan.maas.qianwenaiapi.com/compatible-mode/v1"


def _messages_to_payload(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            payload.append({"role": "system", "content": m.content})
        elif m.role == "user":
            payload.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            item: Dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                item["tool_calls"] = m.tool_calls
            payload.append(item)
        elif m.role == "tool":
            payload.append(
                {
                    "role": "tool",
                    "content": m.content,
                    "tool_call_id": m.tool_call_id or "",
                }
            )
        else:
            payload.append({"role": "user", "content": f"[{m.role}]\n{m.content}"})
    return payload


def _parse_tool_calls(message: Any) -> List[ToolCallRequest]:
    raw = getattr(message, "tool_calls", None) or []
    out: List[ToolCallRequest] = []
    for tc in raw:
        fn = getattr(tc, "function", None)
        if not fn:
            continue
        name = getattr(fn, "name", "") or ""
        args_raw = getattr(fn, "arguments", "") or "{}"
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
        except json.JSONDecodeError:
            args = {"_raw": args_raw}
        if not isinstance(args, dict):
            args = {"value": args}
        out.append(
            ToolCallRequest(
                id=getattr(tc, "id", "") or "",
                name=name,
                arguments=args,
            )
        )
    return out


class DashScopeChatModel(ChatModel):
    """通过 OpenAI 兼容接口调用通义千问系列。"""

    provider = "dashscope"

    def __init__(
        self,
        model_id: str,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 90.0,
    ) -> None:
        self.model_id = model_id
        self._api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self._base_url = base_url or os.getenv(
            "DASHSCOPE_COMPAT_BASE_URL", DEFAULT_BASE_URL
        )
        if not self._api_key:
            logger.warning("未设置 DASHSCOPE_API_KEY，模型调用会失败")
        self._client = OpenAI(
            api_key=self._api_key or "missing",
            base_url=self._base_url,
            timeout=timeout,
        )

    def complete(
        self,
        messages: List[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        tools: Optional[Sequence[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> ModelResult:
        payload = _messages_to_payload(messages)
        kwargs: dict = {
            "model": self.model_id,
            "messages": payload,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if stop:
            kwargs["stop"] = stop
        if tools:
            kwargs["tools"] = list(tools)
            kwargs["tool_choice"] = tool_choice or "auto"

        t0 = time.time()
        span = get_tracer().current
        logger.debug(
            "DashScope 请求 model=%s msgs=%s tools=%s",
            self.model_id,
            len(payload),
            len(tools or []),
        )
        resp = self._client.chat.completions.create(**kwargs)
        latency_ms = (time.time() - t0) * 1000

        choice = resp.choices[0]
        msg = choice.message
        content = (msg.content or "").strip()
        tool_calls = _parse_tool_calls(msg)
        usage = getattr(resp, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        metrics = get_metrics()
        metrics.incr("llm_calls_total", model=self.model_id, provider=self.provider)
        metrics.observe("llm_latency_ms", latency_ms, model=self.model_id)
        metrics.incr("llm_prompt_tokens_total", value=prompt_tokens, model=self.model_id)
        metrics.incr(
            "llm_completion_tokens_total", value=completion_tokens, model=self.model_id
        )
        if span:
            span.add_event(
                "llm_usage",
                model=self.model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=round(latency_ms, 2),
                tool_calls=len(tool_calls),
            )

        return ModelResult(
            content=content,
            model=self.model_id,
            provider=self.provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            ttft_ms=None,
            tool_calls=tool_calls,
            raw=resp,
        )
