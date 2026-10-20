"""多轮对话：仅做独立检索问句改写（不再做意图分流）。

设计说明
--------
- 旧逻辑用 intent(qa/chitchat/...) 短路，容易把「语料相关追问」误判成闲聊，
  导致不走检索。现改为：一律改写成可独立检索的 standalone_query，再检索语料；
  语料无命中时由检索层返回「没有相关信息」。
- standalone_query 会作为 RAG 答案缓存的主键之一：改写会把「它/上面」补全，
  同一事实问法在不同轮次更容易收敛到同一缓存键（反而提高命中率）。
"""
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_utils import make_dashscope_chat, normalize_llm_text
from app.core import rag_trace


def _chat_model():
    model = os.getenv('DASHSCOPE_FAST_MODEL', 'qwen-plus')
    return make_dashscope_chat(model=model, temperature=0.1)


def _format_history(context: List[Dict[str, Any]], max_turns: int = 5) -> str:
    if not context:
        return '（无历史对话）'
    lines: List[str] = []
    for msg in context[-max_turns * 2:]:
        role = msg.get('role', 'user')
        content = (msg.get('content') or '')[:800]
        lines.append(f"{role}: {content}")
    return '\n'.join(lines)


def _parse_json_block(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group(0))
        raise


def understand_query(
    user_input: str,
    context: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    将用户当前输入改写为可独立用于检索的完整问句。

    返回（保持字段兼容旧调用方）:
    - standalone_query: 独立检索问句（必有；失败时回退原文）
    - intent: 固定为 "qa"（已废弃意图识别，仅为兼容）
    - reply_hint: 恒为空（无结果提示由检索层给出）
    """
    context = context or []
    history = _format_history(context)
    user_input = (user_input or '').strip()

    system = SystemMessage(content=(
        "你是 RAG 问答系统的查询改写模块。根据多轮对话历史，把用户当前输入改写成"
        "一句可独立检索的完整问句（补全指代、省略的主语/宾语）。"
        "只输出 JSON，不要 markdown。不要判断意图，不要拒绝回答。"
    ))
    human = HumanMessage(content=f"""最近对话:
{history}

当前用户输入:
{user_input}

请输出 JSON:
{{
  "standalone_query": "补全后的独立完整问句；若原文已完整则可与原文相同"
}}

规则:
1. 「它/这个/上面说的/刚才」等指代必须结合历史补全为明确对象
2. 不要添加用户未提及的约束；不要回答问题本身
3. 保持与用户相同的语言（中文/英文）
""")

    t0 = time.perf_counter()
    try:
        chat = _chat_model()
        resp = chat.invoke([system, human])
        data = _parse_json_block(normalize_llm_text(resp.content))
        standalone = (data.get('standalone_query') or user_input).strip()
        result = {
            'intent': 'qa',
            'standalone_query': standalone or user_input,
            'reply_hint': '',
        }
        rag_trace.emit(
            'query_understanding',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'user_input': rag_trace.truncate_text(user_input),
                'standalone_query': rag_trace.truncate_text(result['standalone_query']),
                'rewrote': result['standalone_query'] != user_input,
                'fallback': False,
            },
        )
        return result
    except Exception as e:
        print(f"⚠️  query_understanding 失败，回退原文: {e}")
        result = {
            'intent': 'qa',
            'standalone_query': user_input,
            'reply_hint': '',
        }
        rag_trace.emit(
            'query_understanding',
            status='error',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'user_input': rag_trace.truncate_text(user_input),
                'standalone_query': rag_trace.truncate_text(result['standalone_query']),
                'fallback': True,
            },
            message=str(e),
            error_type=type(e).__name__,
        )
        return result
