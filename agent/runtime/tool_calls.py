"""工具调用数据结构（原生 function calling + 执行器共用）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agent.models.base import ModelResult, ToolCallRequest


@dataclass
class ToolCallSpec:
    """一次工具调用（单步可含多个）。"""

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    depends_on: List[str] = field(default_factory=list)


def specs_from_model_result(result: ModelResult) -> List[ToolCallSpec]:
    """把 Provider 解析后的 tool_calls 转为执行器输入。"""
    out: List[ToolCallSpec] = []
    for i, tc in enumerate(result.tool_calls):
        cid = tc.id or f"call_{i + 1}"
        out.append(ToolCallSpec(name=tc.name, arguments=dict(tc.arguments), call_id=cid))
    return out


def openai_tool_calls_payload(tool_calls: List[ToolCallRequest]) -> List[Dict[str, Any]]:
    """assistant 消息里回传的 tool_calls 字段（OpenAI 形状）。"""
    payload: List[Dict[str, Any]] = []
    for tc in tool_calls:
        payload.append(
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
        )
    return payload


def format_observations(results: List[Dict[str, Any]]) -> str:
    """把多工具结果拼成可读文本（记忆 / Plan-Execute 仍用）。"""
    if not results:
        return "(无工具结果)"
    if len(results) == 1:
        r = results[0]
        return str(r.get("content", ""))
    lines = []
    for r in results:
        cid = r.get("call_id") or ""
        name = r.get("tool") or ""
        content = r.get("content", "")
        prefix = f"[{cid} {name}]" if cid else f"[{name}]"
        lines.append(f"{prefix} {content}")
    return "\n".join(lines)
