"""BM25 稀疏检索（Hybrid 混合检索的稀疏路）。"""
import os
import re
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

from rank_bm25 import BM25Okapi

from app.models.document import DocumentChunkModel
from app.core import rag_trace

# BM25Okapi 默认 k1=1.5, b=0.75（Okapi BM25）


def _use_jieba() -> bool:
    return os.getenv('BM25_USE_JIEBA', 'true').lower() == 'true'


@lru_cache(maxsize=1)
def _jieba_cut(text: str) -> Tuple[str, ...]:
    import jieba
    return tuple(t.strip().lower() for t in jieba.cut(text) if t.strip())


def tokenize(text: str) -> List[str]:
    """
    中英文分词，供 BM25 使用。
    中文优先 jieba；英文/数字按词切分。
    """
    text = (text or '').strip()
    if not text:
        return []

    tokens: List[str] = []

    if _use_jieba():
        try:
            for seg in _jieba_cut(text):
                if re.match(r'^[\u4e00-\u9fff]+$', seg):
                    if len(seg) >= 1:
                        tokens.append(seg)
                elif re.match(r'^[a-z0-9]+$', seg) and len(seg) >= 2:
                    tokens.append(seg)
            if tokens:
                return tokens
        except Exception:
            pass

    # fallback：英文词 + 中文单字（二元组）
    for part in re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]', text.lower()):
        if re.match(r'[a-z0-9]+', part):
            if len(part) >= 2:
                tokens.append(part)
        else:
            tokens.append(part)
    return tokens


def _candidate_limit() -> int:
    return int(os.getenv('BM25_CANDIDATE_LIMIT', '2000'))


def bm25_search(
    user_id: int,
    query: str,
    top_k: int = 20,
    file_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    对用户已入库切片构建 BM25 索引并检索 top_k。
    MySQL 提供语料；打分由 rank_bm25.BM25Okapi 完成。
    """
    t0 = time.perf_counter()
    query_tokens = tokenize(query)
    if not query_tokens:
        rag_trace.emit(
            'bm25_search',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'query': rag_trace.truncate_text(query),
                'top_k': top_k,
                'file_ids': file_ids,
                'hits': 0,
                'chunks': [],
                'reason': 'empty_query_tokens',
            },
        )
        return []

    try:
        chunks = DocumentChunkModel.search_chunks_by_user(
            user_id=user_id,
            file_ids=file_ids,
            limit=_candidate_limit(),
        )
        if not chunks:
            rag_trace.emit(
                'bm25_search',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    'query': rag_trace.truncate_text(query),
                    'top_k': top_k,
                    'file_ids': file_ids,
                    'hits': 0,
                    'chunks': [],
                    'reason': 'no_candidates',
                },
            )
            return []

        corpus_tokens: List[List[str]] = []
        valid_chunks: List[Dict[str, Any]] = []
        for chunk in chunks:
            text = chunk.get('chunk_text') or ''
            toks = tokenize(text)
            if not toks:
                continue
            corpus_tokens.append(toks)
            valid_chunks.append(chunk)

        if not corpus_tokens:
            rag_trace.emit(
                'bm25_search',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    'query': rag_trace.truncate_text(query),
                    'top_k': top_k,
                    'file_ids': file_ids,
                    'hits': 0,
                    'chunks': [],
                    'reason': 'empty_corpus_tokens',
                },
            )
            return []

        bm25 = BM25Okapi(corpus_tokens)
        scores = bm25.get_scores(query_tokens)

        scored: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(valid_chunks):
            score = float(scores[idx])
            if score <= 0:
                continue
            file_id = chunk['file_id']
            chunk_index = chunk['chunk_index']
            text = chunk.get('chunk_text') or ''
            scored.append({
                'id': f"user_{user_id}_file_{file_id}_chunk_{chunk_index}",
                'file_id': file_id,
                'chunk_index': chunk_index,
                'content': text,
                'chunk_text': text,
                'score': score,
                'metadata': {
                    'file_id': file_id,
                    'chunk_index': chunk_index,
                    'page_numbers': chunk.get('page_numbers') or [],
                    'retrieval': 'bm25',
                },
                'source': 'bm25',
            })

        scored.sort(key=lambda x: x['score'], reverse=True)
        result = scored[:top_k]
        rag_trace.emit(
            'bm25_search',
            latency_ms=(time.perf_counter() - t0) * 1000,
            data={
                'query': rag_trace.truncate_text(query),
                'top_k': top_k,
                'file_ids': file_ids,
                'candidate_count': len(valid_chunks),
                'hits': len(result),
                'chunks': rag_trace.summarize_chunks(result),
            },
        )
        return result
    except Exception as e:
        rag_trace.emit(
            'bm25_search',
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


# 兼容旧名
def keyword_search(
    user_id: int,
    query: str,
    top_k: int = 20,
    file_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    return bm25_search(user_id, query, top_k, file_ids)
