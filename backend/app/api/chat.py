"""对话相关API

问答缓存约定
------------
- 缓存键基于改写后的 standalone_query（见 qa_cache），与 session 窗口分离。
- 命中缓存时仍 _persist_messages，保证当前会话历史不断档。
- 清除会话只删 session:*:context / DB，不会删 rag:qa:*。
"""
import asyncio
import json
import uuid
from typing import Generator, List, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatQueryRequest, ChatQueryResponse, ChatHistoryResponse,
    ChatSessionResponse, ChatSessionListResponse, ChatMessage, ChatSource
)
from app.schemas.user import MessageResponse
from app.models.chat import ChatSessionModel, ChatMessageModel
from app.core.security import get_current_user
from app.core.rag import rag_service
from app.core.redis_manager import redis_manager
from app.core.retrieval_pipeline import retrieve_context, empty_retrieval_reply
from app.core.query_understanding import understand_query
from app.core.qa_cache import get_cached_answer, set_cached_answer
from app.core import rag_trace
from app.core.session_memory import max_context_turns

router = APIRouter(prefix="/api/chat", tags=["对话"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _load_session_context(session_id: str) -> list:
    """Redis 滑动窗口（最近 N 轮）；冷启动时从 DB 回填。"""
    context = redis_manager.get_session_context(session_id)
    if context:
        return context
    limit = max_context_turns() * 2
    messages = ChatMessageModel.get_recent_messages(session_id, limit=limit)
    for msg in messages:
        redis_manager.save_session_message(
            session_id, msg['role'], msg['content'], msg.get('sources')
        )
    return redis_manager.get_session_context(session_id)


def _hits_to_sources(chunks: list) -> list:
    sources = []
    for doc in chunks:
        meta = doc.get('metadata') or {}
        sources.append(
            ChatSource(
                content=(doc.get('content') or doc.get('chunk_text') or '')[:2000],
                score=float(doc.get('rrf_score') or doc.get('score') or 0),
                metadata=meta,
            )
        )
    return sources


def _sources_to_dict(sources: List[ChatSource]) -> list:
    return [s.model_dump() for s in sources]


def _dict_to_sources(raw: list | None) -> List[ChatSource]:
    """把 QA 缓存里的 sources JSON 还原为 ChatSource。"""
    sources: List[ChatSource] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        sources.append(
            ChatSource(
                content=(item.get("content") or "")[:2000],
                score=float(item.get("score") or 0),
                metadata=item.get("metadata") or {},
            )
        )
    return sources


def _persist_messages(
    session_id: str,
    query: str,
    answer: str,
    sources: List[ChatSource],
) -> None:
    sources_dict = _sources_to_dict(sources)
    ChatMessageModel.create_message(session_id, 'user', query)
    redis_manager.save_session_message(session_id, 'user', query)
    ChatMessageModel.create_message(session_id, 'assistant', answer, sources_dict)
    redis_manager.save_session_message(session_id, 'assistant', answer, sources_dict)
    ChatSessionModel.update_session_timestamp(session_id)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ensure_session(user_id: int, query: str, session_id: Optional[str]) -> str:
    if not session_id:
        session_id = str(uuid.uuid4())
        ChatSessionModel.create_session(session_id, user_id, title=query[:30] or "新对话")
        return session_id

    session = ChatSessionModel.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session['user_id'] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该会话")
    return session_id


def _stream_query_events(
    user_id: int,
    query: str,
    session_id: str,
    file_ids: Optional[List[int]],
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> Generator[str, None, None]:
    request_id = rag_trace.new_request_id()

    def _bind_trace() -> None:
        # SSE 在线程池不同线程间 resume，每次关键步骤前重新绑定
        rag_trace.set_trace_context(
            request_id, user_id=user_id, session_id=session_id
        )

    try:
        _bind_trace()
        rag_trace.emit(
            'request_start',
            data={
                'query': rag_trace.truncate_text(query),
                'session_id': session_id,
                'file_ids': file_ids,
                'mode': 'stream',
                'request_id': request_id,
                'vector_weight': vector_weight,
                'bm25_weight': bm25_weight,
            },
        )
        yield _sse_event("meta", {"session_id": session_id, "request_id": request_id})
        yield _sse_event("status", {"phase": "retrieving"})

        _bind_trace()
        context = _load_session_context(session_id)

        # 1) 改写 → 2) 查 QA 缓存（命中则跳过检索+生成，但仍写入本会话）
        understood = understand_query(query, context)
        standalone = (understood.get("standalone_query") or query).strip()
        cached = get_cached_answer(
            user_id,
            standalone,
            file_ids=file_ids,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )
        if cached:
            answer = (cached.get("answer") or "").strip() or empty_retrieval_reply()
            sources = _dict_to_sources(cached.get("sources"))
            yield _sse_event("status", {"phase": "generating", "cache_hit": True})
            yield _sse_event("delta", {"content": answer})
            _persist_messages(session_id, query, answer, sources)
            rag_trace.finish(
                status="ok",
                query=rag_trace.truncate_text(query),
                skip_answer=False,
                cache_hit=True,
                standalone_query=rag_trace.truncate_text(standalone),
                answer_preview=rag_trace.truncate_text(answer),
                answer_len=len(answer),
                sources=rag_trace.summarize_chunks([
                    {
                        "content": s.content,
                        "score": s.score,
                        "metadata": s.metadata or {},
                        "file_id": (s.metadata or {}).get("file_id"),
                        "chunk_index": (s.metadata or {}).get("chunk_index"),
                        "source": (s.metadata or {}).get("retrieval"),
                    }
                    for s in sources
                ]),
            )
            yield _sse_event("done", {
                "session_id": session_id,
                "request_id": request_id,
                "answer": answer,
                "sources": _sources_to_dict(sources),
                "cache_hit": True,
            })
            return

        retrieval = retrieve_context(
            user_id=user_id,
            user_input=query,
            session_context=context,
            file_ids=file_ids,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            standalone_query=standalone,
        )

        sources: List[ChatSource] = []
        answer_parts: List[str] = []
        yield _sse_event("status", {"phase": "generating", "cache_hit": False})

        _bind_trace()
        if retrieval.get('skip_answer'):
            answer = retrieval.get('reply_hint') or empty_retrieval_reply()
            yield _sse_event("delta", {"content": answer})
            answer_parts.append(answer)
        else:
            chunks = retrieval.get('chunks') or []
            sources = _hits_to_sources(chunks)
            for delta in rag_service.generate_answer_stream(
                query,
                chunks,
                history=context,
            ):
                answer_parts.append(delta)
                yield _sse_event("delta", {"content": delta})

        _bind_trace()
        answer = ''.join(answer_parts).strip() or "抱歉，未能生成有效回答。"
        _persist_messages(session_id, query, answer, sources)

        # 仅成功检索并生成时写入 QA 缓存（无命中语料不缓存）
        if not retrieval.get("skip_answer"):
            set_cached_answer(
                user_id,
                retrieval.get("standalone_query") or standalone,
                answer=answer,
                sources=_sources_to_dict(sources),
                file_ids=file_ids,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
            )

        rag_trace.finish(
            status='ok',
            query=rag_trace.truncate_text(query),
            skip_answer=bool(retrieval.get('skip_answer')),
            cache_hit=False,
            standalone_query=rag_trace.truncate_text(
                retrieval.get("standalone_query") or standalone
            ),
            answer_preview=rag_trace.truncate_text(answer),
            answer_len=len(answer),
            sources=rag_trace.summarize_chunks([
                {
                    'content': s.content,
                    'score': s.score,
                    'metadata': s.metadata or {},
                    'file_id': (s.metadata or {}).get('file_id'),
                    'chunk_index': (s.metadata or {}).get('chunk_index'),
                    'source': (s.metadata or {}).get('retrieval'),
                }
                for s in sources
            ]),
        )

        yield _sse_event("done", {
            "session_id": session_id,
            "request_id": request_id,
            "answer": answer,
            "sources": _sources_to_dict(sources),
            "cache_hit": False,
        })
    except Exception as e:
        print(f"❌ chat_query_stream 失败: {e}")
        import traceback
        traceback.print_exc()
        _bind_trace()
        rag_trace.finish(
            status='error',
            query=rag_trace.truncate_text(query),
            error_type=type(e).__name__,
            message=str(e),
        )
        yield _sse_event("error", {
            "message": f"查询失败: {str(e)}",
            "request_id": request_id,
        })
    finally:
        rag_trace.clear_trace_context()


def _process_query_sync(
    user_id: int,
    query: str,
    session_id: str,
    file_ids: list | None,
    vector_weight: float | None = None,
    bm25_weight: float | None = None,
) -> dict:
    with rag_trace.rag_request(user_id=user_id, session_id=session_id) as request_id:
        rag_trace.emit(
            'request_start',
            data={
                'query': rag_trace.truncate_text(query),
                'session_id': session_id,
                'file_ids': file_ids,
                'mode': 'sync',
                'request_id': request_id,
                'vector_weight': vector_weight,
                'bm25_weight': bm25_weight,
            },
        )
        try:
            context = _load_session_context(session_id)

            understood = understand_query(query, context)
            standalone = (understood.get("standalone_query") or query).strip()
            cached = get_cached_answer(
                user_id,
                standalone,
                file_ids=file_ids,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
            )
            if cached:
                answer = (cached.get("answer") or "").strip() or empty_retrieval_reply()
                sources = _dict_to_sources(cached.get("sources"))
                _persist_messages(session_id, query, answer, sources)
                rag_trace.finish(
                    status="ok",
                    query=rag_trace.truncate_text(query),
                    skip_answer=False,
                    cache_hit=True,
                    standalone_query=rag_trace.truncate_text(standalone),
                    answer_preview=rag_trace.truncate_text(answer),
                    answer_len=len(answer),
                    sources=rag_trace.summarize_chunks([
                        {
                            "content": s.content,
                            "score": s.score,
                            "metadata": s.metadata or {},
                            "file_id": (s.metadata or {}).get("file_id"),
                            "chunk_index": (s.metadata or {}).get("chunk_index"),
                            "source": (s.metadata or {}).get("retrieval"),
                        }
                        for s in sources
                    ]),
                )
                return {
                    "answer": answer,
                    "sources": sources,
                    "session_id": session_id,
                    "request_id": request_id,
                    "cache_hit": True,
                }

            retrieval = retrieve_context(
                user_id=user_id,
                user_input=query,
                session_context=context,
                file_ids=file_ids,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
                standalone_query=standalone,
            )

            if retrieval.get('skip_answer'):
                answer = retrieval.get('reply_hint') or empty_retrieval_reply()
                sources = []
            else:
                chunks = retrieval.get('chunks') or []
                answer = rag_service.generate_answer(
                    query,
                    chunks,
                    history=context,
                )
                sources = _hits_to_sources(chunks)
                set_cached_answer(
                    user_id,
                    retrieval.get("standalone_query") or standalone,
                    answer=answer,
                    sources=_sources_to_dict(sources),
                    file_ids=file_ids,
                    vector_weight=vector_weight,
                    bm25_weight=bm25_weight,
                )

            _persist_messages(session_id, query, answer, sources)

            rag_trace.finish(
                status='ok',
                query=rag_trace.truncate_text(query),
                skip_answer=bool(retrieval.get('skip_answer')),
                cache_hit=False,
                standalone_query=rag_trace.truncate_text(
                    retrieval.get("standalone_query") or standalone
                ),
                answer_preview=rag_trace.truncate_text(answer),
                answer_len=len(answer),
                sources=rag_trace.summarize_chunks([
                    {
                        'content': s.content,
                        'score': s.score,
                        'metadata': s.metadata or {},
                        'file_id': (s.metadata or {}).get('file_id'),
                        'chunk_index': (s.metadata or {}).get('chunk_index'),
                        'source': (s.metadata or {}).get('retrieval'),
                    }
                    for s in sources
                ]),
            )

            return {
                'answer': answer,
                'sources': sources,
                'session_id': session_id,
                'request_id': request_id,
                'cache_hit': False,
            }
        except Exception as e:
            rag_trace.finish(
                status='error',
                query=rag_trace.truncate_text(query),
                error_type=type(e).__name__,
                message=str(e),
            )
            raise


@router.post("/query/stream")
async def chat_query_stream(
    request: ChatQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """SSE 流式问答：检索完成后逐 token 返回答案。"""
    user_id = current_user['id']
    query = request.query.strip()
    file_ids = request.file_ids

    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题不能为空")

    session_id = _ensure_session(user_id, query, request.session_id)
    vector_weight = request.vector_weight
    bm25_weight = request.bm25_weight
    if vector_weight is not None and bm25_weight is None:
        bm25_weight = max(0.0, 1.0 - float(vector_weight))

    return StreamingResponse(
        _stream_query_events(
            user_id, query, session_id, file_ids, vector_weight, bm25_weight
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/query", response_model=ChatQueryResponse)
async def chat_query(
    request: ChatQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """发送查询并获取回答（非流式，兼容旧客户端）"""
    user_id = current_user['id']
    query = request.query.strip()
    file_ids = request.file_ids

    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题不能为空")

    session_id = _ensure_session(user_id, query, request.session_id)
    vector_weight = request.vector_weight
    bm25_weight = request.bm25_weight
    if vector_weight is not None and bm25_weight is None:
        bm25_weight = max(0.0, 1.0 - float(vector_weight))

    try:
        result = await asyncio.to_thread(
            _process_query_sync,
            user_id,
            query,
            session_id,
            file_ids,
            vector_weight,
            bm25_weight,
        )
        return ChatQueryResponse(
            answer=result['answer'],
            sources=result['sources'],
            session_id=result['session_id'],
        )
    except Exception as e:
        print(f"❌ chat_query 失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {str(e)}"
        )


@router.get("/sessions", response_model=ChatSessionListResponse)
async def get_sessions(current_user: dict = Depends(get_current_user)):
    """获取用户的所有会话"""
    user_id = current_user['id']
    sessions = ChatSessionModel.get_user_sessions(user_id)

    session_responses = [
        ChatSessionResponse(
            session_id=session['session_id'],
            title=session['title'],
            created_at=session['created_at'],
            updated_at=session['updated_at'],
            last_message=session.get('last_message'),
        )
        for session in sessions
    ]

    return ChatSessionListResponse(
        total=len(session_responses),
        sessions=session_responses
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取会话的对话历史"""
    user_id = current_user['id']

    session = ChatSessionModel.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session['user_id'] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该会话")

    messages = ChatMessageModel.get_session_messages(session_id)

    chat_messages = []
    for msg in messages:
        sources = None
        if msg.get('sources'):
            sources = [ChatSource(**s) for s in msg['sources']]
        chat_messages.append(
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=msg['created_at'],
                sources=sources
            )
        )

    return ChatHistoryResponse(session_id=session_id, messages=chat_messages)


@router.delete("/session/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除会话"""
    user_id = current_user['id']

    session = ChatSessionModel.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session['user_id'] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该会话")

    # 只清会话窗口 + DB；不动 rag:qa:* 答案缓存
    ChatSessionModel.delete_session(session_id)
    redis_manager.clear_session_context(session_id)

    return MessageResponse(success=True, message="会话已删除")


@router.delete("/clear", response_model=MessageResponse)
async def clear_all_sessions(current_user: dict = Depends(get_current_user)):
    """清空所有会话"""
    user_id = current_user['id']
    sessions = ChatSessionModel.get_user_sessions(user_id)

    for session in sessions:
        sid = session['session_id']
        # 只清 session:*:context，与 QA 缓存命名空间隔离
        ChatSessionModel.delete_session(sid)
        redis_manager.clear_session_context(sid)

    return MessageResponse(
        success=True,
        message=f"已清空 {len(sessions)} 个会话"
    )
