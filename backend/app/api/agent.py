"""Agent 薄 API：鉴权 + SSE 转发；不写 chat_* / Milvus。

会话状态（memory/pending/skills）默认由 MainAgent 写入 Redis（agent:* 前缀），
与 RAG 的 session:* / rag:qa:* 隔离。
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.agent_service import get_main_agent
from app.core.security import get_current_user
from app.schemas.agent import AgentQueryRequest
from app.schemas.user import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_agent(
    *,
    user_id: str,
    query: str,
    session_id: Optional[str],
    mode: str,
    resume_token: Optional[str],
    answers,
) -> AsyncIterator[str]:
    agent = get_main_agent()
    try:
        if resume_token:
            if not session_id:
                yield _sse("error", {"message": "resume 需要 session_id"})
                return
            payload = answers if answers is not None else query
            stream = agent.astream_resume(
                payload,
                session_id=session_id,
                user_id=user_id,
                resume_token=resume_token,
            )
        else:
            stream = agent.astream(
                query,
                session_id=session_id,
                user_id=user_id,
                mode=mode,  # type: ignore[arg-type]
            )

        async for ev in stream:
            yield ev.to_sse()
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent stream 失败")
        yield _sse("error", {"message": f"Agent 失败: {exc}"})


@router.post("/query/stream")
async def agent_query_stream(
    request: AgentQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """SSE：meta/status/log → 日志栏；delta/needs_input/done → 聊天栏。"""
    query = (request.query or "").strip()
    if not query and not request.resume_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="问题不能为空",
        )

    user_id = str(current_user.get("id") or "")
    mode = request.mode if request.mode in ("react", "plan_execute") else "react"

    return StreamingResponse(
        _stream_agent(
            user_id=user_id,
            query=query or "",
            session_id=request.session_id,
            mode=mode,
            resume_token=request.resume_token,
            answers=request.answers,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.delete("/session/{session_id}", response_model=MessageResponse)
async def clear_agent_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """清空指定 Agent 会话的 memory / pending / skills（默认 Redis，不写 DB）。

    只删 agent:mem:* / agent:pending:* / agent:skills:*，
    不影响 RAG 的 session:*:context 与 rag:qa:*。
    """
    del current_user  # 仅要求已登录
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id 不能为空",
        )
    agent = get_main_agent()
    if hasattr(agent, "clear_session_state"):
        agent.clear_session_state(sid)
    else:
        agent.memory.clear(sid)
        agent.pending_store.clear(sid)
    logger.info("已清空 Agent 会话 session=%s", sid)
    return MessageResponse(success=True, message="Agent 会话已清空")
