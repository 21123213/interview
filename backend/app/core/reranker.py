"""DashScope TextReRank（专用重排模型，不是对话 LLM）。

在 RRF 融合后的候选池上，对 (query, document) 做 pairwise 相关性打分并重排。
调用的是百炼 TextReRank API（如 gte-rerank-v2 / qwen3-rerank），
与 qwen-max 等生成模型无关。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from dashscope import TextReRank
from http import HTTPStatus


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _api_key() -> str:
    """与项目其它 DashScope 调用对齐：优先通用 key，其次 embedding key。"""
    return (
        (os.getenv('DASHSCOPE_API_KEY') or '').strip()
        or (os.getenv('DASHSCOPE_EMBEDDING_API_KEY') or '').strip()
    )


def _rerank_model() -> str:
    # gte-rerank 旧版将下线；默认 v2。可改为 qwen3-rerank。
    return (os.getenv('RERANK_MODEL') or 'gte-rerank-v2').strip()


def _chunk_text(chunk: Dict[str, Any]) -> str:
    return (chunk.get('content') or chunk.get('chunk_text') or '').strip()


def _truncate_doc(text: str, max_chars: int) -> str:
    """避免单条文档过长触发 API 400（按字符粗截断，非精确 token）。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]


def dashscope_rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    *,
    top_n: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    用 DashScope TextReRank 对候选 chunks 重排。

    返回:
      (重排后的 chunks, meta)
      meta 含 model / top_n / usage 等，供 rag_trace 使用。
      失败时抛出异常，由调用方决定是否回退到 RRF 截断。
    """
    if not chunks:
        return [], {'model': _rerank_model(), 'top_n': 0, 'input_docs': 0}

    answer_k = top_n if top_n is not None else _env_int('ANSWER_TOP_K', 10)
    answer_k = max(1, min(answer_k, len(chunks)))

    max_chars = _env_int('RERANK_MAX_DOC_CHARS', 6000)
    documents: List[str] = []
    valid_indices: List[int] = []
    for i, chunk in enumerate(chunks):
        text = _truncate_doc(_chunk_text(chunk), max_chars)
        if not text:
            continue
        documents.append(text)
        valid_indices.append(i)

    if not documents:
        # 全空文档：保持原序截断
        return [dict(c) for c in chunks[:answer_k]], {
            'model': _rerank_model(),
            'top_n': answer_k,
            'input_docs': 0,
            'reason': 'empty_documents',
        }

    key = _api_key()
    if not key:
        raise RuntimeError('DASHSCOPE_API_KEY / DASHSCOPE_EMBEDDING_API_KEY 未配置，无法调用 TextReRank')

    model = _rerank_model()
    # top_n：让 API 返回全部有效文档的分数，本地再截到 answer_k，便于写完整 trace
    resp = TextReRank.call(
        model=model,
        query=query,
        documents=documents,
        top_n=len(documents),
        return_documents=False,
        api_key=key,
    )

    if getattr(resp, 'status_code', None) != HTTPStatus.OK:
        raise RuntimeError(
            f"TextReRank 失败 status={getattr(resp, 'status_code', None)} "
            f"code={getattr(resp, 'code', None)} message={getattr(resp, 'message', '')}"
        )

    output = getattr(resp, 'output', None) or {}
    results = output.get('results') if isinstance(output, dict) else getattr(output, 'results', None)
    if not results:
        raise RuntimeError('TextReRank 返回空 results')

    # results: [{index, relevance_score}, ...]，index 对应本次 documents 列表下标
    scored: List[Tuple[float, int]] = []
    for item in results:
        if isinstance(item, dict):
            idx = int(item.get('index', -1))
            score = float(item.get('relevance_score') or 0.0)
        else:
            idx = int(getattr(item, 'index', -1))
            score = float(getattr(item, 'relevance_score', 0.0) or 0.0)
        if 0 <= idx < len(valid_indices):
            scored.append((score, valid_indices[idx]))

    scored.sort(key=lambda x: x[0], reverse=True)

    reranked: List[Dict[str, Any]] = []
    for score, orig_i in scored[:answer_k]:
        item = dict(chunks[orig_i])
        item['rerank_score'] = score
        # 下游 / 前端若读 score，优先看到重排分；保留原 rrf_score
        item['score'] = score
        meta = dict(item.get('metadata') or {})
        meta['retrieval'] = 'rerank'
        meta['rerank_model'] = model
        item['metadata'] = meta
        item['source'] = 'rerank'
        reranked.append(item)

    usage = getattr(resp, 'usage', None) or {}
    total_tokens = (
        usage.get('total_tokens') if isinstance(usage, dict)
        else getattr(usage, 'total_tokens', None)
    )

    meta_out: Dict[str, Any] = {
        'model': model,
        'top_n': answer_k,
        'input_docs': len(documents),
        'scored_docs': len(scored),
        'total_tokens': total_tokens,
        'request_id': getattr(resp, 'request_id', None),
    }
    return reranked, meta_out
