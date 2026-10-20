"""RAG 问答结果缓存（与 session 对话窗口完全分离的命名空间）。

命名空间对照（切勿混用 clear）
--------------------------------
- session:{sid}:context
    多轮对话滑动窗口；前端「清除会话」只删这个。
- rag:qa:{user_id}:...
    「改写后问句 + 语料世代 + 检索/模型配置」→ 答案/sources；
    清会话不会碰它；语料变更靠 corpus_ver，时间靠 TTL。
- user:{user_id}:corpus_ver
    用户语料世代计数；上传完成/删除/重嵌入成功时 INCR。

缓存键设计
----------
rag:qa:{user_id}:{corpus_ver}:{scope}:{cfg_fp}:{query_hash}

- standalone_query：query_understanding 改写后的独立问句（再 normalize）
- scope：当前业务默认全量文档 → "all"；若请求带 file_ids 则写入排序后的 id 列表
- cfg_fp：expand_n / topK / RRF_K / 融合权重 / embedding+answer 模型名指纹
  （改 .env 后自然 miss，避免脏读）
- TTL：默认 3600 秒（1 小时）

可观测性
--------
每次 get/set 都会 rag_trace.emit('qa_cache', ...) 并打日志，字段含 hit、
standalone_query、corpus_ver、cfg_fp、key 后缀，便于评估命中率。
改写会把多轮指代收敛到同一 standalone，通常比「用原文当 key」更容易命中。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.core import rag_trace
from app.core.redis_manager import redis_manager

logger = logging.getLogger("app.core.qa_cache")

# 与 session:* 严格分离的前缀
_QA_PREFIX = "rag:qa"
_CORPUS_VER_KEY = "user:{user_id}:corpus_ver"

# 默认 1 小时
_DEFAULT_TTL = 3600


def cache_enabled() -> bool:
    return os.getenv("RAG_QA_CACHE_ENABLED", "true").lower() == "true"


def cache_ttl_seconds() -> int:
    try:
        return max(60, int(os.getenv("RAG_QA_CACHE_TTL", str(_DEFAULT_TTL))))
    except (TypeError, ValueError):
        return _DEFAULT_TTL


def normalize_query(text: str) -> str:
    """缓存键用的问句归一化：去首尾空白、压缩中间空白。"""
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def retrieval_config_fingerprint(
    *,
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> str:
    """
    检索/生成相关配置指纹。配置变更 → 指纹变 → 旧缓存自动 miss。

    包含：问句扩写条数、各路 topK、RRF、融合权重、embedding/answer 模型。
    """
    vw = vector_weight if vector_weight is not None else _env_float("RRF_VECTOR_WEIGHT", 0.5)
    bw = bm25_weight if bm25_weight is not None else _env_float("RRF_BM25_WEIGHT", 0.5)
    payload = {
        "expand_n": _env_int("QUERY_EXPAND_N", 3),
        "per_path": _env_int("RETRIEVE_TOP_K_PER_PATH", 20),
        "rrf_per_query": _env_int("RRF_PER_QUERY", 15),
        "rrf_final": _env_int("RRF_FINAL", 15),
        "answer_top_k": _env_int("ANSWER_TOP_K", 10),
        "rrf_k": _env_int("RRF_K", 60),
        "vector_weight": round(float(vw), 4),
        "bm25_weight": round(float(bw), 4),
        # 开关或模型变更都要换指纹，避免旧缓存跳过重排结果
        "rerank": os.getenv("RERANK_ENABLED", "false").lower(),
        "rerank_model": os.getenv("RERANK_MODEL", "gte-rerank-v2"),
        "embed_model": os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4"),
        "answer_model": os.getenv("DASHSCOPE_ANSWER_MODEL", "qwen-max"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def file_scope_token(file_ids: Optional[List[int]]) -> str:
    """
    文档范围：未传 / 空列表视为全量 all；
    若显式传入 file_ids，则用排序后的 id 列表，避免顺序导致 key 不一致。
    """
    if not file_ids:
        return "all"
    return "f_" + "_".join(str(i) for i in sorted(int(x) for x in file_ids))


def get_corpus_version(user_id: int) -> int:
    """读取用户语料世代；不存在则视为 0。"""
    key = _CORPUS_VER_KEY.format(user_id=user_id)
    raw = redis_manager.client.get(key)
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def bump_corpus_version(user_id: int) -> int:
    """
    语料变更时调用：上传向量化完成 / 删除文件 / 重嵌入成功。

    INCR 后旧 rag:qa key 因 ver 对不上而自然 miss，无需 SCAN 删全库。
    返回新的版本号。
    """
    key = _CORPUS_VER_KEY.format(user_id=user_id)
    new_ver = int(redis_manager.client.incr(key))
    logger.info("corpus_ver bumped user_id=%s -> %s", user_id, new_ver)
    rag_trace.emit(
        "corpus_version",
        data={"user_id": user_id, "corpus_ver": new_ver, "action": "bump"},
    )
    return new_ver


def invalidate_user_qa_cache(user_id: int) -> int:
    """
    主动让该用户全部 QA 缓存失效：再 bump 一次 corpus_ver 即可。

    不扫描 rag:qa:*，也不触碰 session:*:context。
    """
    return bump_corpus_version(user_id)


def build_cache_key(
    user_id: int,
    standalone_query: str,
    *,
    file_ids: Optional[List[int]] = None,
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> Dict[str, Any]:
    """组装完整 key 及可观测元数据（不访问 Redis）。"""
    corpus_ver = get_corpus_version(user_id)
    scope = file_scope_token(file_ids)
    cfg_fp = retrieval_config_fingerprint(
        vector_weight=vector_weight, bm25_weight=bm25_weight
    )
    norm_q = normalize_query(standalone_query)
    query_hash = hashlib.sha256(norm_q.encode("utf-8")).hexdigest()[:24]
    key = f"{_QA_PREFIX}:{user_id}:{corpus_ver}:{scope}:{cfg_fp}:{query_hash}"
    return {
        "key": key,
        "user_id": user_id,
        "corpus_ver": corpus_ver,
        "scope": scope,
        "cfg_fp": cfg_fp,
        "query_hash": query_hash,
        "standalone_query_norm": norm_q,
    }


def get_cached_answer(
    user_id: int,
    standalone_query: str,
    *,
    file_ids: Optional[List[int]] = None,
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    读取 QA 缓存。命中返回 {"answer": str, "sources": list}；未命中返回 None。

    注意：与 session 上下文无关；命中后仍应由调用方把本轮问答写入 session。
    """
    if not cache_enabled():
        rag_trace.emit("qa_cache", data={"hit": False, "reason": "disabled"})
        return None

    meta = build_cache_key(
        user_id,
        standalone_query,
        file_ids=file_ids,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
    )
    raw = redis_manager.client.get(meta["key"])
    if not raw:
        logger.info(
            "qa_cache MISS user=%s ver=%s scope=%s cfg=%s q=%s",
            user_id,
            meta["corpus_ver"],
            meta["scope"],
            meta["cfg_fp"],
            meta["standalone_query_norm"][:80],
        )
        rag_trace.emit(
            "qa_cache",
            data={
                "hit": False,
                "user_id": user_id,
                "corpus_ver": meta["corpus_ver"],
                "scope": meta["scope"],
                "cfg_fp": meta["cfg_fp"],
                "query_hash": meta["query_hash"],
                "standalone_query": rag_trace.truncate_text(standalone_query),
                "key_suffix": meta["key"].split(":")[-1],
            },
        )
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("qa_cache corrupt key=%s", meta["key"])
        redis_manager.client.delete(meta["key"])
        rag_trace.emit(
            "qa_cache",
            status="error",
            data={"hit": False, "reason": "corrupt", "key": meta["key"]},
        )
        return None

    logger.info(
        "qa_cache HIT user=%s ver=%s scope=%s cfg=%s q=%s",
        user_id,
        meta["corpus_ver"],
        meta["scope"],
        meta["cfg_fp"],
        meta["standalone_query_norm"][:80],
    )
    rag_trace.emit(
        "qa_cache",
        data={
            "hit": True,
            "user_id": user_id,
            "corpus_ver": meta["corpus_ver"],
            "scope": meta["scope"],
            "cfg_fp": meta["cfg_fp"],
            "query_hash": meta["query_hash"],
            "standalone_query": rag_trace.truncate_text(standalone_query),
            "answer_len": len(payload.get("answer") or ""),
            "sources_count": len(payload.get("sources") or []),
            "key_suffix": meta["key"].split(":")[-1],
        },
    )
    return payload


def set_cached_answer(
    user_id: int,
    standalone_query: str,
    *,
    answer: str,
    sources: List[Dict[str, Any]],
    file_ids: Optional[List[int]] = None,
    vector_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> None:
    """写入 QA 缓存（仅成功生成且非 skip_answer 的路径应调用）。"""
    if not cache_enabled():
        return
    answer = (answer or "").strip()
    if not answer:
        return

    meta = build_cache_key(
        user_id,
        standalone_query,
        file_ids=file_ids,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
    )
    payload = {
        "answer": answer,
        "sources": sources or [],
        "standalone_query": standalone_query,
    }
    ttl = cache_ttl_seconds()
    redis_manager.client.setex(
        meta["key"],
        ttl,
        json.dumps(payload, ensure_ascii=False),
    )
    logger.info(
        "qa_cache SET user=%s ver=%s ttl=%s q=%s",
        user_id,
        meta["corpus_ver"],
        ttl,
        meta["standalone_query_norm"][:80],
    )
    rag_trace.emit(
        "qa_cache",
        data={
            "action": "set",
            "user_id": user_id,
            "corpus_ver": meta["corpus_ver"],
            "scope": meta["scope"],
            "cfg_fp": meta["cfg_fp"],
            "query_hash": meta["query_hash"],
            "ttl": ttl,
            "standalone_query": rag_trace.truncate_text(standalone_query),
            "answer_len": len(answer),
            "sources_count": len(sources or []),
        },
    )
