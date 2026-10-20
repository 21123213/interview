"""组装 needs_input 结果：transcript + trace span + 日志。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer
from agent.runtime.param_check import ParamGap
from agent.runtime.pending import (
    PendingState,
    PendingStore,
    compose_user_answer,
    questions_from_gaps,
)
from agent.runtime.result import AgentRunResult

logger = logging.getLogger("agent.runtime.needs_input")


def emit_needs_input(
    *,
    session_id: str,
    trace_id: str,
    mode: str,
    gaps: List[ParamGap],
    user_input: str,
    payload: Dict[str, Any],
    transcript: List[Dict[str, Any]],
    steps: int,
    store: PendingStore,
) -> AgentRunResult:
    """写 pending、打日志/span/transcript，返回 status=needs_input。"""
    questions = questions_from_gaps(gaps)
    source = gaps[0].source if gaps else "user_gap"
    # 若混有 user_gap 与 upstream_gap，优先对人展示 user_gap 问句
    if any(g.source == "user_gap" for g in gaps):
        source = "user_gap"
        questions = questions_from_gaps([g for g in gaps if g.source == "user_gap"])
    answer = compose_user_answer(questions, source)
    state = PendingState(
        mode=mode,
        source=source,
        questions=questions,
        user_input=user_input,
        payload=payload,
    )
    store.put(session_id, state)

    fields = ",".join(
        sorted({f.field for g in gaps for f in g.fields if not f.field.startswith("_")})
    )
    tools = ",".join(sorted({g.tool for g in gaps}))
    logger.info(
        "needs_input mode=%s source=%s tools=%s fields=%s session=%s",
        mode,
        source,
        tools,
        fields,
        session_id,
    )
    get_metrics().incr("needs_input_total", mode=mode, source=source)

    with get_tracer().span(
        "needs_input",
        source=source,
        tools=tools,
        fields=fields,
        mode=mode,
        resume_token=state.resume_token,
    ) as sp:
        sp.add_event(
            "needs_input",
            source=source,
            tools=tools,
            fields=fields,
            question_count=len(questions),
        )
        # 状态留给 contextmanager 收尾；attrs 标记 needs_input
        sp.status = "needs_input"

    step_log: Dict[str, Any] = {
        "phase": "needs_input",
        "source": source,
        "tools": tools,
        "fields": fields,
        "questions": [q.to_dict() for q in questions],
        "answer_preview": answer[:200],
        "resume_token": state.resume_token,
    }
    transcript.append(step_log)

    root = get_tracer().root
    return AgentRunResult(
        answer=answer,
        session_id=session_id,
        trace_id=trace_id,
        steps=steps,
        status="needs_input",
        user_input=user_input,
        transcript=transcript,
        pending=state.public_dict(),
        trace_tree=root.to_dict() if root else None,
    )
