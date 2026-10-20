"""用户补参解析：结构化输入直读；口语多字段用 fast 模型抽取；规则兜底。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from agent.models.base import ChatMessage
from agent.models.router import ModelRole, ModelRouter
from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer
from agent.runtime.pending import AskQuestion, parse_user_answers_rules
from agent.runtime.plan_schema import _extract_json_obj

logger = logging.getLogger("agent.runtime.answer_parser")

_EXTRACT_SYSTEM = """你是参数抽取器。根据「待填字段列表」从用户回复里提取各字段的值。

规则：
- 只输出一个 JSON 对象，键用 field（字段名），值为从用户原话中提取的字符串
- 用户未提及或无法确定的字段不要出现在 JSON 里，不要编造
- 可略去「目的地是」「出发日期」等引导词，保留日期、地名、数字等实质内容
- 若用户用一句话同时回答多项，尽量拆到对应 field
- 不要输出 markdown 代码块以外的解释文字

示例：
问题 [{"id":"q1","field":"destination","prompt":"目的地？"},{"id":"q2","field":"start_date","prompt":"出发日期？"}]
用户：下周三去杭州玩三天
输出：{"destination":"杭州","start_date":"下周三"}"""


def _llm_parse_enabled() -> bool:
    return os.getenv("AGENT_ANSWER_PARSE_LLM", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _expand_answer_keys(questions: List[AskQuestion], field_values: Dict[str, str]) -> Dict[str, str]:
    """把 {field: value} 展开为同时含 question.id 与 field 的键，供 merge 使用。"""
    out: Dict[str, str] = {}
    field_to_q: Dict[str, List[AskQuestion]] = {}
    id_to_q = {q.id: q for q in questions}
    for q in questions:
        field_to_q.setdefault(q.field, []).append(q)

    for key, val in field_values.items():
        text = str(val).strip()
        if not text:
            continue
        if key in id_to_q:
            q = id_to_q[key]
            out[q.id] = text
            out[q.field] = text
            continue
        for q in field_to_q.get(key, []):
            out[q.id] = text
            out[q.field] = text
    return out


def _rules_cover_all(questions: List[AskQuestion], answers: Dict[str, str]) -> bool:
    """规则解析是否已填满所有真实参数字段。"""
    for q in questions:
        if q.field.startswith("_"):
            continue
        if not (answers.get(q.id) or answers.get(q.field)):
            return False
    return True


def _try_structured_raw(raw: Any) -> Optional[Dict[str, str]]:
    """dict / JSON 字符串 → 直接规范化。"""
    if isinstance(raw, dict):
        field_values = {str(k): str(v).strip() for k, v in raw.items() if v is not None}
        return field_values or None
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            field_values = {
                str(k): str(v).strip() for k, v in data.items() if v is not None
            }
            return field_values or None
    except json.JSONDecodeError:
        pass
    return None


def _normalize_llm_payload(
    questions: List[AskQuestion],
    payload: Dict[str, Any],
) -> Dict[str, str]:
    """只保留与当前问题列表匹配的 field / id。"""
    allowed_fields = {q.field for q in questions if not q.field.startswith("_")}
    allowed_ids = {q.id for q in questions}
    field_values: Dict[str, str] = {}
    for key, val in payload.items():
        if val is None:
            continue
        k = str(key).strip()
        text = str(val).strip()
        if not text:
            continue
        if k in allowed_ids:
            q = next(x for x in questions if x.id == k)
            field_values[q.field] = text
        elif k in allowed_fields:
            field_values[k] = text
    return field_values


async def _extract_with_llm(
    questions: List[AskQuestion],
    text: str,
    router: ModelRouter,
) -> Dict[str, str]:
    """用 fast 模型从自然语言抽取 {field: value}。"""
    spec = [
        {"id": q.id, "field": q.field, "prompt": q.prompt}
        for q in questions
        if not q.field.startswith("_")
    ]
    if not spec:
        return {}

    user = json.dumps(
        {"questions": spec, "user_reply": text},
        ensure_ascii=False,
    )
    model = router.get(ModelRole.FAST, route_reason="answer_extract")
    with get_tracer().span("answer.parse_llm", question_count=len(spec)):
        result = await asyncio.to_thread(
            model.complete,
            [
                ChatMessage(role="system", content=_EXTRACT_SYSTEM),
                ChatMessage(role="user", content=user),
            ],
            temperature=0.0,
            max_tokens=256,
        )
    payload = _extract_json_obj(result.content or "")
    if not payload:
        logger.warning("补参 LLM 未返回合法 JSON: %s", (result.content or "")[:200])
        get_metrics().incr("answer_parse_total", method="llm", status="bad_json")
        return {}
    field_values = _normalize_llm_payload(questions, payload)
    if field_values:
        get_metrics().incr("answer_parse_total", method="llm", status="ok")
        logger.info(
            "补参 LLM 抽取 fields=%s",
            ",".join(sorted(field_values.keys())),
        )
    else:
        get_metrics().incr("answer_parse_total", method="llm", status="empty")
    return field_values


async def aparse_user_answers(
    questions: List[AskQuestion],
    raw: Any,
    router: Optional[ModelRouter] = None,
) -> Dict[str, str]:
    """解析用户补参回复。

    优先级：
    1. dict / JSON（API、表单）
    2. 规则解析；若已填满所有字段则直接返回
    3. fast 模型抽取（多问、口语一句答多项）
    4. 规则结果兜底（含「整段塞第一问」）
    """
    if not questions:
        return {}

    structured = _try_structured_raw(raw)
    if structured is not None:
        get_metrics().incr("answer_parse_total", method="structured", status="ok")
        return _expand_answer_keys(questions, structured)

    rules = parse_user_answers_rules(questions, raw)
    if _rules_cover_all(questions, rules):
        get_metrics().incr("answer_parse_total", method="rules", status="ok")
        return rules

    text = str(raw or "").strip()
    if (
        router is not None
        and _llm_parse_enabled()
        and text
        and len(questions) > 1
    ):
        try:
            llm_fields = await _extract_with_llm(questions, text, router)
            if llm_fields:
                llm_answers = _expand_answer_keys(questions, llm_fields)
                if _rules_cover_all(questions, llm_answers):
                    return llm_answers
                # 部分命中：LLM 优先，规则补空缺
                merged = dict(rules)
                merged.update(llm_answers)
                if _rules_cover_all(questions, merged):
                    get_metrics().incr("answer_parse_total", method="llm+rules", status="ok")
                    return merged
                if llm_answers:
                    get_metrics().incr("answer_parse_total", method="llm", status="partial")
                    return merged
        except Exception:
            logger.exception("补参 LLM 抽取失败，回退规则解析")
            get_metrics().incr("answer_parse_total", method="llm", status="error")

    get_metrics().incr("answer_parse_total", method="rules", status="fallback")
    return rules
