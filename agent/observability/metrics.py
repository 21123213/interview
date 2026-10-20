"""进程内指标注册表：延迟、token、错误率、重试、熔断等。

当前实现为内存累加，便于终端调试打印；后续可导出 Prometheus。
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class _Counter:
    value: float = 0.0


@dataclass
class _Histogram:
    """简易直方图：只保留样本列表，调试时算均值 / 分位。"""

    samples: List[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        self.samples.append(float(value))

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def sum(self) -> float:
        return sum(self.samples)

    @property
    def avg(self) -> float:
        return self.sum / self.count if self.count else 0.0


class MetricsRegistry:
    """线程安全的简易指标库。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, _Counter] = defaultdict(_Counter)
        self._histograms: Dict[str, _Histogram] = defaultdict(_Histogram)

    def incr(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key].value += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._histograms[key].observe(value)

    def snapshot(self) -> Dict[str, object]:
        """导出当前指标快照，供 CLI 打印。"""
        with self._lock:
            counters = {k: v.value for k, v in self._counters.items()}
            histograms = {
                k: {
                    "count": h.count,
                    "sum": round(h.sum, 3),
                    "avg": round(h.avg, 3),
                }
                for k, h in self._histograms.items()
            }
        return {"counters": counters, "histograms": histograms}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()

    @staticmethod
    def _key(name: str, labels: Dict[str, str]) -> str:
        if not labels:
            return name
        parts = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{parts}}}"


_metrics = MetricsRegistry()


def get_metrics() -> MetricsRegistry:
    return _metrics
