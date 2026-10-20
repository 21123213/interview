"""RRF（Reciprocal Rank Fusion）融合多路检索结果。"""
from typing import Any, Callable, Dict, List, Optional, Sequence


def chunk_key(hit: Dict[str, Any]) -> str:
    """切片去重键：优先 Milvus id，否则 file_id + chunk_index。"""
    if hit.get('id'):
        return str(hit['id'])
    return f"{hit.get('file_id')}_{hit.get('chunk_index')}"


def rrf_fuse(
    ranked_lists: List[List[Dict[str, Any]]],
    top_n: int = 15,
    k: int = 60,
    key_fn: Callable[[Dict[str, Any]], str] = chunk_key,
    weights: Optional[Sequence[float]] = None,
) -> List[Dict[str, Any]]:
    """
    对多路已排序列表做 RRF 融合（可加权）。

    标准加权 RRF（rank 从 1 开始）:
      score(doc) = Σ  w_i * ( 1 / (k + rank_i) )
    即：先除以 (k+rank) 得到该路原始 RRF 分，再乘该路权重 w_i。
    weights 与 ranked_lists 一一对应；缺省则各路等权 1.0。
    """
    if not ranked_lists:
        return []

    n = len(ranked_lists)
    if weights is None:
        ws = [1.0] * n
    else:
        ws = [float(w) for w in weights]
        if len(ws) < n:
            ws.extend([1.0] * (n - len(ws)))
        elif len(ws) > n:
            ws = ws[:n]
        # 全非正则退回等权，避免除零
        if sum(max(0.0, w) for w in ws) <= 0:
            ws = [1.0] * n
        else:
            ws = [max(0.0, w) for w in ws]

    scores: Dict[str, float] = {}
    best_hit: Dict[str, Dict[str, Any]] = {}

    for ranked, weight in zip(ranked_lists, ws):
        if not ranked or weight <= 0:
            continue
        for rank, hit in enumerate(ranked, start=1):
            key = key_fn(hit)
            # 先 1/(k+rank)，再乘权重（与 weight/(k+rank) 等价）
            rrf_raw = 1.0 / (k + rank)
            scores[key] = scores.get(key, 0.0) + weight * rrf_raw
            if key not in best_hit:
                best_hit[key] = hit

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results: List[Dict[str, Any]] = []
    for key, rrf_score in ordered[:top_n]:
        item = dict(best_hit[key])
        item['rrf_score'] = rrf_score
        results.append(item)
    return results
