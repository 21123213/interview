"""RAG 问答检索主流程：问句改写 → 多 query 扩写 → 双路召回 → 多层 RRF。

不再做意图分流：一律按语料检索；无命中则 skip_answer + 固定「没有相关信息」提示。
"""
import contextvars
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from app.core.fusion import rrf_fuse
from app.core.keyword_retrieval import bm25_search
from app.core.milvus_service import milvus_service
from app.core.query_expand import expand_queries
from app.core.query_understanding import understand_query
from app.core.rag import embed_text
from app.core.reranker import dashscope_rerank
from app.core import rag_trace


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _normalize_fusion_weights(
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> tuple[float, float]:
    """
    归一化向量/BM25 权重，和为 1。
    未传参时读环境变量 RRF_VECTOR_WEIGHT / RRF_BM25_WEIGHT（默认各 0.5）。
    """
    vw = vector_weight if vector_weight is not None else _env_float('RRF_VECTOR_WEIGHT', 0.5)
    bw = bm25_weight if bm25_weight is not None else _env_float('RRF_BM25_WEIGHT', 0.5)
    vw = max(0.0, float(vw))
    bw = max(0.0, float(bw))
    total = vw + bw
    if total <= 0:
        return 0.5, 0.5
    return vw / total, bw / total


def _submit(executor: ThreadPoolExecutor, fn, *args):
    """在子线程中保留 contextvars（含 request_id）。"""
    ctx = contextvars.copy_context()
    return executor.submit(ctx.run, fn, *args)


def _vector_search(
    user_id: int,
    query: str,
    top_k: int,
    file_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    t0 = time.perf_counter()
    if not milvus_service.enabled:
        rag_trace.emit(
            'vector_search',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'query': rag_trace.truncate_text(query),
                'top_k': top_k,
                'file_ids': file_ids,
                'hits': 0,
                'chunks': [],
                'milvus_enabled': False,
            },
        )
        return []
    try:
        embedding = embed_text(query)
        hits = milvus_service.search(
            user_id=user_id,
            query_embedding=embedding,
            top_k=top_k,
            file_ids=file_ids,
        )
        formatted: List[Dict[str, Any]] = []
        for hit in hits:
            text = hit.get('chunk_text') or ''
            formatted.append({
                'id': hit.get('id'),
                'file_id': hit.get('file_id'),
                'chunk_index': hit.get('chunk_index'),
                'content': text,
                'chunk_text': text,
                'score': float(hit.get('score') or hit.get('distance') or 0),
                'metadata': {
                    **(hit.get('metadata') or {}),
                    'file_id': hit.get('file_id'),
                    'chunk_index': hit.get('chunk_index'),
                    'retrieval': 'vector',
                },
                'source': 'vector',
            })
        rag_trace.emit(
            'vector_search',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'query': rag_trace.truncate_text(query),
                'top_k': top_k,
                'file_ids': file_ids,
                'hits': len(formatted),
                'chunks': rag_trace.summarize_chunks(formatted),
                'milvus_enabled': True,
            },
        )
        return formatted
    except Exception as e:
        rag_trace.emit(
            'vector_search',
            status='error',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'query': rag_trace.truncate_text(query),
                'top_k': top_k,
                'file_ids': file_ids,
                'hits': 0,
            },
            message=str(e),
            error_type=type(e).__name__,
        )
        raise


def _retrieve_for_single_query(
    user_id: int,
    query: str,
    file_ids: Optional[List[int]] = None,
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """单问：向量 top-K + BM25 top-K → 加权 RRF → 每问最多 RRF_PER_QUERY 条。"""
    per_path = _env_int('RETRIEVE_TOP_K_PER_PATH', 20)
    per_query = _env_int('RRF_PER_QUERY', 15)
    rrf_k = _env_int('RRF_K', 60)
    vw, bw = _normalize_fusion_weights(vector_weight, bm25_weight)
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = _submit(executor, _vector_search, user_id, query, per_path, file_ids)
        bm25_future = _submit(executor, bm25_search, user_id, query, per_path, file_ids)
        vector_hits = vector_future.result()
        bm25_hits = bm25_future.result()

    fused = rrf_fuse(
        [vector_hits, bm25_hits],
        top_n=per_query,
        k=rrf_k,
        weights=[vw, bw],
    )
    rag_trace.emit(
        'rrf_per_query',
        latency_ms=(time.perf_counter() - t0) * 1000,
        data={
            'query': rag_trace.truncate_text(query),
            'vector_hits': len(vector_hits),
            'bm25_hits': len(bm25_hits),
            'fused_hits': len(fused),
            'per_path': per_path,
            'per_query': per_query,
            'vector_weight': vw,
            'bm25_weight': bw,
            'chunks': rag_trace.summarize_chunks(fused),
        },
    )
    return fused


def retrieve_context(
    user_id: int,
    user_input: str,
    session_context: Optional[List[Dict[str, Any]]] = None,
    file_ids: Optional[List[int]] = None,
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
    standalone_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    检索流水线：
    1) 问句改写（可传入已算好的 standalone_query，避免与 QA 缓存层重复打 LLM）
    2) 问句扩写 → 每变式双路召回 → 问内 RRF → 跨问 RRF
    3) 无命中则 skip_answer（不编造）

    返回:
    - query / standalone_query / expanded_queries
    - chunks / skip_answer / reply_hint
    """
    t0 = time.perf_counter()
    vw, bw = _normalize_fusion_weights(vector_weight, bm25_weight)
    user_input = (user_input or '').strip()

    if not user_input and not (standalone_query or '').strip():
        rag_trace.emit(
            'rrf_final',
            data={'skip_answer': True, 'hits': 0, 'chunks': [], 'reason': 'empty_query'},
        )
        return {
            'query': '',
            'standalone_query': '',
            'expanded_queries': [],
            'chunks': [],
            'skip_answer': True,
            'reply_hint': '问题不能为空，请输入与文档相关的问题。',
            'vector_weight': vw,
            'bm25_weight': bw,
        }

    # --- 改写：未预计算时在此调用 ---
    if standalone_query is None:
        understood = understand_query(user_input, session_context)
        standalone = (understood.get('standalone_query') or user_input).strip()
    else:
        standalone = standalone_query.strip() or user_input

    expand_n = _env_int('QUERY_EXPAND_N', 3)
    expanded = expand_queries(standalone, n=expand_n)
    if not expanded:
        expanded = [standalone]

    # 各变式并行检索
    per_query_lists: List[List[Dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(expanded))) as executor:
        futures = [
            _submit(
                executor,
                _retrieve_for_single_query,
                user_id,
                q,
                file_ids,
                vw,
                bw,
            )
            for q in expanded
        ]
        for fut in futures:
            per_query_lists.append(fut.result())

    final_n = _env_int('RRF_FINAL', 15)
    rrf_k = _env_int('RRF_K', 60)
    fused = rrf_fuse(per_query_lists, top_n=final_n, k=rrf_k)

    rerank_enabled = os.getenv('RERANK_ENABLED', 'false').lower() == 'true'
    if rerank_enabled:
        chunks = _rerank(standalone, fused)
    else:
        answer_k = _env_int('ANSWER_TOP_K', 10)
        chunks = fused[:answer_k]

    if not chunks:
        rag_trace.emit(
            'rrf_final',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'skip_answer': True,
                'query': rag_trace.truncate_text(user_input),
                'standalone_query': rag_trace.truncate_text(standalone),
                'expanded_queries': [rag_trace.truncate_text(q) for q in expanded],
                'hits': 0,
                'chunks': [],
                'file_ids': file_ids,
                'reason': 'no_hits',
                'vector_weight': vw,
                'bm25_weight': bw,
            },
        )
        return {
            'query': user_input,
            'standalone_query': standalone,
            'expanded_queries': expanded,
            'chunks': [],
            'skip_answer': True,
            'reply_hint': empty_retrieval_reply(),
            'vector_weight': vw,
            'bm25_weight': bw,
        }

    rag_trace.emit(
        'rrf_final',
        latency_ms=(time.perf_counter() - t0) * 1000,
        data={
            'skip_answer': False,
            'query': rag_trace.truncate_text(user_input),
            'standalone_query': rag_trace.truncate_text(standalone),
            'expanded_queries': [rag_trace.truncate_text(q) for q in expanded],
            'rerank_enabled': rerank_enabled,
            'fused_before_cut': len(fused),
            'top_k': len(chunks),
            'hits': len(chunks),
            'chunks': rag_trace.summarize_chunks(chunks),
            'file_ids': file_ids,
            'vector_weight': vw,
            'bm25_weight': bw,
        },
    )

    return {
        'query': user_input,
        'standalone_query': standalone,
        'expanded_queries': expanded,
        'chunks': chunks,
        'skip_answer': False,
        'reply_hint': '',
        'vector_weight': vw,
        'bm25_weight': bw,
    }


def _rerank(query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    RRF 之后的 Cross-Encoder 重排：调用 DashScope TextReRank API。

    失败时回退为按 rrf_score 截断到 ANSWER_TOP_K，保证问答链路不中断。
    """
    answer_k = _env_int('ANSWER_TOP_K', 10)
    t0 = time.perf_counter()
    if not chunks:
        rag_trace.emit(
            'rerank',
            latency_ms=0.0,
            data={'hits': 0, 'top_k': answer_k, 'provider': 'dashscope'},
        )
        return []

    try:
        reranked, meta = dashscope_rerank(query, chunks, top_n=answer_k)
        rag_trace.emit(
            'rerank',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'provider': 'dashscope',
                'query': rag_trace.truncate_text(query),
                'hits': len(reranked),
                'top_k': answer_k,
                'chunks': rag_trace.summarize_chunks(reranked),
                **meta,
            },
        )
        return reranked
    except Exception as e:
        # API / 网络异常：降级为 RRF 顺序截断，并记录错误便于排查
        fallback = [dict(c) for c in chunks[:answer_k]]
        rag_trace.emit(
            'rerank',
            status='error',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'provider': 'dashscope',
                'query': rag_trace.truncate_text(query),
                'hits': len(fallback),
                'top_k': answer_k,
                'fallback': 'rrf_truncate',
                'chunks': rag_trace.summarize_chunks(fallback),
            },
            message=str(e),
            error_type=type(e).__name__,
        )
        return fallback


def empty_retrieval_reply() -> str:
    """检索无结果时的默认回复。"""
    return (
        '抱歉，我没有在您的文档中找到相关信息。'
        '请确认已上传并处理完成相关文件，或换个问法再试。'
    )
