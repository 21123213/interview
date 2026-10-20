"""按依赖维度的熔断器。

key 建议：tool:xxx / model:provider:model_id
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer

logger = logging.getLogger("agent.resilience.circuit")


class CircuitState(str, Enum):
    CLOSED = "closed"  # 正常放行
    OPEN = "open"  # 快速失败
    HALF_OPEN = "half_open"  # 探测恢复


class CircuitOpenError(RuntimeError):
    """熔断打开时抛出；调用方应做降级或直接失败。"""

    def __init__(self, dependency: str) -> None:
        self.dependency = dependency
        super().__init__(f"熔断已打开，拒绝调用: {dependency}")


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5  # 连续失败多少次后打开
    recovery_timeout_sec: float = 30.0  # open 多久后进入 half_open
    half_open_success_threshold: int = 1  # half_open 成功几次后关闭


class CircuitBreaker:
    """单个依赖的熔断器。"""

    def __init__(self, dependency: str, config: Optional[CircuitBreakerConfig] = None) -> None:
        self.dependency = dependency
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float = 0.0
        self._half_open_successes = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    def before_call(self) -> None:
        """调用前检查；open 则抛 CircuitOpenError。"""
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == CircuitState.OPEN:
                get_metrics().incr(
                    "circuit_reject_total", dependency=self.dependency
                )
                raise CircuitOpenError(self.dependency)

    def on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.config.half_open_success_threshold:
                    self._to_closed()
            else:
                self._consecutive_failures = 0

    def on_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == CircuitState.HALF_OPEN:
                self._to_open()
            elif self._consecutive_failures >= self.config.failure_threshold:
                self._to_open()

    def _maybe_transition_to_half_open(self) -> None:
        if self._state != CircuitState.OPEN:
            return
        if time.time() - self._opened_at >= self.config.recovery_timeout_sec:
            self._state = CircuitState.HALF_OPEN
            self._half_open_successes = 0
            logger.info("熔断半开(探测): %s", self.dependency)
            get_metrics().incr("circuit_half_open_total", dependency=self.dependency)
            span = get_tracer().current
            if span:
                span.add_event("circuit_half_open", dependency=self.dependency)

    def _to_open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        logger.warning("熔断打开: %s failures=%s", self.dependency, self._consecutive_failures)
        get_metrics().incr("circuit_open_total", dependency=self.dependency)
        span = get_tracer().current
        if span:
            span.add_event("circuit_open", dependency=self.dependency)

    def _to_closed(self) -> None:
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        logger.info("熔断关闭(恢复): %s", self.dependency)
        get_metrics().incr("circuit_close_total", dependency=self.dependency)
        span = get_tracer().current
        if span:
            span.add_event("circuit_close", dependency=self.dependency)


class CircuitBreakerRegistry:
    """按 dependency 字符串管理多个熔断器。"""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None) -> None:
        self._config = config or CircuitBreakerConfig()
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get(self, dependency: str) -> CircuitBreaker:
        with self._lock:
            if dependency not in self._breakers:
                self._breakers[dependency] = CircuitBreaker(dependency, self._config)
            return self._breakers[dependency]


_registry = CircuitBreakerRegistry()


def get_circuit_registry() -> CircuitBreakerRegistry:
    return _registry
