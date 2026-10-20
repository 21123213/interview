"""RAG 分阶段可观测日志：request_id 串联 + JSONL + 控制台摘要。"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_request_id: ContextVar[Optional[str]] = ContextVar('rag_request_id', default=None)
_session_id: ContextVar[Optional[str]] = ContextVar('rag_session_id', default=None)
_user_id: ContextVar[Optional[int]] = ContextVar('rag_user_id', default=None)
_started_at: ContextVar[Optional[float]] = ContextVar('rag_started_at', default=None)

_write_lock = threading.Lock()
_DEFAULT_PREVIEW_LEN = 200


def _enabled() -> bool:
    return os.getenv('RAG_TRACE_ENABLED', 'true').lower() == 'true'


def _full_mode() -> bool:
    return os.getenv('RAG_TRACE_FULL', 'false').lower() == 'true'


def full_mode() -> bool:
    """是否写入完整 chunk / prompt 文本。"""
    return _full_mode()


def _trace_dir() -> Path:
    raw = os.getenv('RAG_TRACE_DIR', 'logs')
    path = Path(raw)
    if not path.is_absolute():
        # backend 工作目录或仓库根均可；相对路径相对当前 cwd
        path = Path.cwd() / path
    return path


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def get_request_id() -> Optional[str]:
    return _request_id.get()


def set_trace_context(
    request_id: str,
    *,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> None:
    _request_id.set(request_id)
    if user_id is not None:
        _user_id.set(user_id)
    if session_id is not None:
        _session_id.set(session_id)
    _started_at.set(time.perf_counter())


def clear_trace_context() -> None:
    _request_id.set(None)
    _session_id.set(None)
    _user_id.set(None)
    _started_at.set(None)


@contextmanager
def rag_request(
    *,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Iterator[str]:
    """
    绑定本请求的 trace context，退出时清理。

    注意：SSE 流式可能在线程池不同线程间 resume generator，
    不能用 ContextVar Token.reset（会跨 Context 报错），改用 set/clear。
    """
    rid = request_id or new_request_id()
    set_trace_context(rid, user_id=user_id, session_id=session_id)
    try:
        yield rid
    finally:
        clear_trace_context()


def truncate_text(text: Any, max_len: int = _DEFAULT_PREVIEW_LEN) -> str:
    s = '' if text is None else str(text)
    if _full_mode():
        return s
    if len(s) <= max_len:
        return s
    return s[:max_len] + '…'


def summarize_chunks(
    chunks: Optional[List[Dict[str, Any]]],
    *,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """将检索 hit 压成可写日志的精简结构。"""
    if not chunks:
        return []
    out: List[Dict[str, Any]] = []
    for hit in chunks if limit is None else chunks[:limit]:
        text = hit.get('content') or hit.get('chunk_text') or ''
        meta = hit.get('metadata') or {}
        # 有 rerank_score 时优先记重排分，便于对照 RRF 前后变化
        score = hit.get('rerank_score')
        if score is None:
            score = hit.get('rrf_score') or hit.get('score') or 0
        item: Dict[str, Any] = {
            'id': hit.get('id'),
            'file_id': hit.get('file_id') or meta.get('file_id'),
            'chunk_index': hit.get('chunk_index') if hit.get('chunk_index') is not None else meta.get('chunk_index'),
            'score': float(score),
            'source': hit.get('source') or meta.get('retrieval') or '',
            'preview': truncate_text(text),
        }
        if hit.get('rerank_score') is not None and hit.get('rrf_score') is not None:
            item['rrf_score'] = float(hit['rrf_score'])
            item['rerank_score'] = float(hit['rerank_score'])
        if _full_mode():
            item['content'] = text
        out.append(item)
    return out


def _console_summary(event: Dict[str, Any]) -> str:
    stage = event.get('stage', '')
    rid = event.get('request_id', '-')
    status = event.get('status', 'ok')
    latency = event.get('latency_ms')
    data = event.get('data') or {}
    parts = [f"[rag] request_id={rid} stage={stage} status={status}"]
    if latency is not None:
        parts.append(f"latency_ms={latency}")
    if 'hits' in data:
        parts.append(f"hits={data['hits']}")
    elif 'chunks' in data and isinstance(data['chunks'], list):
        parts.append(f"hits={len(data['chunks'])}")
    if 'intent' in data:
        parts.append(f"intent={data['intent']}")
    if 'expanded_queries' in data and isinstance(data['expanded_queries'], list):
        parts.append(f"queries={len(data['expanded_queries'])}")
    if stage == 'rerank' and data.get('model'):
        parts.append(f"model={data['model']}")
    if 'answer_len' in data:
        parts.append(f"answer_len={data['answer_len']}")
    if status == 'error' and event.get('message'):
        parts.append(f"error={event['message']}")
    return ' '.join(parts)


def _write_jsonl(event: Dict[str, Any]) -> None:
    """写入可读的多行 JSON（事件之间空一行），便于人工翻看。"""
    directory = _trace_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / 'rag_trace.jsonl'
        stage = event.get('stage', '')
        rid = event.get('request_id', '-')
        status = event.get('status', 'ok')
        latency = event.get('latency_ms')
        header = f"# [{stage}] request_id={rid} status={status}"
        if latency is not None:
            header += f" latency_ms={latency}"
        body = json.dumps(event, ensure_ascii=False, indent=2, default=str)
        block = f"{header}\n{body}\n\n"
        with _write_lock:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(block)
    except Exception as e:
        print(f"⚠️  rag_trace 写文件失败: {e}")


def emit(
    stage: str,
    *,
    status: str = 'ok',
    latency_ms: Optional[float] = None,
    data: Optional[Dict[str, Any]] = None,
    message: str = '',
    error_type: str = '',
) -> None:
    """写入一条阶段事件（控制台摘要 + JSONL）。"""
    if not _enabled():
        return

    rid = _request_id.get() or '-'
    event: Dict[str, Any] = {
        'ts': datetime.now(timezone.utc).astimezone().isoformat(timespec='milliseconds'),
        'request_id': rid,
        'session_id': _session_id.get(),
        'user_id': _user_id.get(),
        'stage': stage,
        'status': status,
        'latency_ms': round(latency_ms, 2) if latency_ms is not None else None,
        'data': data or {},
    }
    if message:
        event['message'] = message
    if error_type:
        event['error_type'] = error_type

    print(_console_summary(event))
    _write_jsonl(event)


@contextmanager
def span(stage: str, **extra: Any) -> Iterator[Dict[str, Any]]:
    """计时阶段；with 块内可往 data 字典写字段，退出时自动 emit。"""
    data: Dict[str, Any] = dict(extra)
    t0 = time.perf_counter()
    status = 'ok'
    message = ''
    error_type = ''
    try:
        yield data
    except Exception as e:
        status = 'error'
        message = str(e)
        error_type = type(e).__name__
        data.setdefault('error', True)
        emit(
            stage,
            status=status,
            latency_ms=(time.perf_counter() - t0) * 1000,
            data=data,
            message=message,
            error_type=error_type,
        )
        raise
    else:
        emit(
            stage,
            status=status,
            latency_ms=(time.perf_counter() - t0) * 1000,
            data=data,
            message=message,
            error_type=error_type,
        )


def finish(status: str = 'ok', **data: Any) -> None:
    """请求结束事件，附带总耗时。"""
    started = _started_at.get()
    total_ms = (time.perf_counter() - started) * 1000 if started is not None else None
    message = str(data.pop('message', '') or '')
    error_type = str(data.pop('error_type', '') or '')
    payload = dict(data)
    if total_ms is not None:
        payload['total_latency_ms'] = round(total_ms, 2)
    emit(
        'request_end',
        status=status,
        latency_ms=total_ms,
        data=payload,
        message=message,
        error_type=error_type,
    )
