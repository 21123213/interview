"""指数退避 + 抖动。"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class BackoffPolicy:
    """退避策略参数。

    Attributes:
        base_ms: 首次退避基准毫秒。
        factor: 指数因子，第 n 次约为 base * factor^(n-1)。
        max_ms: 单次退避上限。
        jitter: 是否加随机抖动，避免惊群。
    """

    base_ms: float = 200.0
    factor: float = 2.0
    max_ms: float = 8_000.0
    jitter: bool = True


def compute_backoff_ms(attempt: int, policy: BackoffPolicy) -> float:
    """根据「即将进行的 attempt 编号」（从 1 开始）计算休眠毫秒。

    attempt=1 表示第一次失败后、第二次调用前的等待。
    """
    if attempt < 1:
        attempt = 1
    raw = policy.base_ms * (policy.factor ** (attempt - 1))
    capped = min(raw, policy.max_ms)
    if not policy.jitter:
        return capped
    # 全抖动：在 [0, capped] 均匀取样，更平滑
    return random.uniform(0, capped)
