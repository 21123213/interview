"""会话记忆：保留最近 N 轮完整问答，总 token 超限则压缩。"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.llm_utils import make_dashscope_chat, normalize_llm_text


def max_context_turns() -> int:
    return int(os.getenv('MAX_CONTEXT_TURNS', '3'))


def max_context_tokens() -> int:
    return int(os.getenv('MAX_CONTEXT_TOKENS', '20000'))


def estimate_tokens(text: str) -> int:
    """
    粗估 token：中文按字≈1 token，英文/数字按约 4 字符≈1 token。
    略偏保守，避免实际超窗。
    """
    if not text:
        return 0
    cjk = len(re.findall(r'[\u4e00-\u9fff]', text))
    other = len(text) - cjk
    return cjk + max(1, (other + 3) // 4) if other else cjk


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        total += estimate_tokens(str(msg.get('content') or ''))
        # 角色与分隔符开销
        total += 4
    return total


def trim_to_turns(messages: List[Dict[str, Any]], turns: int | None = None) -> List[Dict[str, Any]]:
    """只保留最近 turns 轮（每轮 user+assistant，最多 turns*2 条）。"""
    turns = turns if turns is not None else max_context_turns()
    max_messages = max(1, turns) * 2
    if len(messages) <= max_messages:
        return list(messages)
    return list(messages[-max_messages:])


def _chat_model() -> ChatOpenAI:
    model = os.getenv('DASHSCOPE_FAST_MODEL', 'qwen-turbo')
    return make_dashscope_chat(model=model, temperature=0.1)


def _hard_truncate_messages(
    messages: List[Dict[str, Any]],
    max_tokens: int,
) -> List[Dict[str, Any]]:
    """从最早消息开始截断内容，直到总 token 不超过上限。"""
    result = [dict(m) for m in messages]
    while result and estimate_messages_tokens(result) > max_tokens:
        # 优先压缩最早一条的 content
        first = result[0]
        content = str(first.get('content') or '')
        tokens = estimate_messages_tokens(result)
        overflow = tokens - max_tokens
        if overflow <= 0:
            break
        # 按字符近似删减
        cut = max(50, overflow + 50)
        if len(content) <= cut:
            result.pop(0)
            continue
        first = dict(first)
        first['content'] = content[: max(0, len(content) - cut)] + '…'
        first['truncated'] = True
        result[0] = first
    return result


def compress_messages(
    messages: List[Dict[str, Any]],
    max_tokens: int | None = None,
) -> List[Dict[str, Any]]:
    """
    将较早轮次压缩为摘要，尽量保留最近一轮完整问答。
    LLM 失败时回退为硬截断。
    """
    max_tokens = max_tokens if max_tokens is not None else max_context_tokens()
    messages = trim_to_turns(messages)
    if estimate_messages_tokens(messages) <= max_tokens:
        return messages

    if len(messages) <= 2:
        return _hard_truncate_messages(messages, max_tokens)

    older = messages[:-2]
    latest = messages[-2:]
    older_text_lines = []
    for msg in older:
        role = msg.get('role', 'user')
        content = msg.get('content') or ''
        older_text_lines.append(f"{role}: {content}")
    older_block = '\n'.join(older_text_lines)

    # 给摘要预留预算：总量的约 40%，其余留给最近一轮
    latest_tokens = estimate_messages_tokens(latest)
    summary_budget = max(200, max_tokens - latest_tokens - 100)
    # 字数预算（偏保守）
    summary_char_budget = max(200, summary_budget)

    try:
        chat = _chat_model()
        system = SystemMessage(content=(
            "你是对话记忆压缩助手。将多轮问答压缩为简洁中文摘要，"
            "保留问题要点、关键事实与结论，去掉重复与寒暄。"
            "只输出摘要正文，不要标题或解释。"
        ))
        human = HumanMessage(content=(
            f"请将以下对话压缩到约 {summary_char_budget} 字以内：\n\n{older_block}"
        ))
        resp = chat.invoke([system, human])
        summary = normalize_llm_text(resp.content).strip()
        if not summary:
            raise ValueError('empty summary')
        if estimate_tokens(summary) > summary_budget:
            # 再硬截
            while estimate_tokens(summary) > summary_budget and len(summary) > 20:
                summary = summary[: int(len(summary) * 0.8)] + '…'
        compressed = [
            {
                'role': 'system',
                'content': f'[此前对话摘要]\n{summary}',
                'compressed': True,
            },
            *latest,
        ]
        if estimate_messages_tokens(compressed) > max_tokens:
            return _hard_truncate_messages(compressed, max_tokens)
        return compressed
    except Exception as e:
        print(f"⚠️  session_memory 压缩失败，回退截断: {e}")
        return _hard_truncate_messages(messages, max_tokens)


def enforce_memory_limits(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """先截到 N 轮，再按 token 上限压缩。"""
    trimmed = trim_to_turns(messages)
    if estimate_messages_tokens(trimmed) <= max_context_tokens():
        return trimmed
    return compress_messages(trimmed)
