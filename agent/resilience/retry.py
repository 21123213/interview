"""统一重试封装（同步 + 异步）。

返回值只有最终结果；中间 attempt 只记日志 / span / metrics。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar, Union

from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer
from agent.resilience.backoff import BackoffPolicy, compute_backoff_ms
from agent.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    get_circuit_registry,
)

logger = logging.getLogger("agent.resilience.retry")

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """重试策略。"""

    max_attempts: int = 3
    backoff: Optional[BackoffPolicy] = None
    retry_on: tuple = (Exception,)
    use_circuit_breaker: bool = True


def call_with_retry(
    dependency: str,
    fn: Callable[[], T],
    policy: Optional[RetryPolicy] = None,
) -> T:
    """同步重试（仍供少数同步路径使用）。"""
    policy = policy or RetryPolicy(backoff=BackoffPolicy())
    breaker: Optional[CircuitBreaker] = None
    if policy.use_circuit_breaker:
        breaker = get_circuit_registry().get(dependency)

    last_exc: Optional[BaseException] = None
    metrics = get_metrics()

    for attempt in range(1, policy.max_attempts + 1):
        if breaker is not None:
            breaker.before_call()

        span = get_tracer().current
        t0 = time.time()
        try:
            result = fn()
            latency_ms = (time.time() - t0) * 1000
            if breaker is not None:
                breaker.on_success()
            metrics.incr("call_success_total", dependency=dependency)
            metrics.observe("call_latency_ms", latency_ms, dependency=dependency)
            if span:
                span.add_event(
                    "call_ok",
                    dependency=dependency,
                    attempt=attempt,
                    latency_ms=round(latency_ms, 2),
                )
            if attempt > 1:
                metrics.incr("call_recovered_total", dependency=dependency)
            return result
        except CircuitOpenError:
            raise
        except policy.retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            latency_ms = (time.time() - t0) * 1000
            err_name = type(exc).__name__
            if breaker is not None:
                breaker.on_failure()
            metrics.incr(
                "call_error_total", dependency=dependency, error=err_name
            )
            logger.warning(
                "调用失败 dependency=%s attempt=%s/%s error=%s: %s",
                dependency,
                attempt,
                policy.max_attempts,
                err_name,
                exc,
            )
            if span:
                span.add_event(
                    "call_attempt_failed",
                    dependency=dependency,
                    attempt=attempt,
                    error_class=err_name,
                    latency_ms=round(latency_ms, 2),
                )

            if attempt >= policy.max_attempts:
                break

            if policy.backoff is not None:
                sleep_ms = compute_backoff_ms(attempt, policy.backoff)
                metrics.observe("backoff_ms", sleep_ms, dependency=dependency)
                logger.info(
                    "退避等待 dependency=%s backoff_ms=%.0f",
                    dependency,
                    sleep_ms,
                )
                if span:
                    span.add_event(
                        "backoff",
                        dependency=dependency,
                        attempt=attempt,
                        backoff_ms=round(sleep_ms, 2),
                    )
                time.sleep(sleep_ms / 1000.0)

    assert last_exc is not None
    metrics.incr("call_final_failure_total", dependency=dependency)
    raise last_exc


async def call_with_retry_async(
    dependency: str,
    fn: Callable[[], Union[T, Awaitable[T]]],
    policy: Optional[RetryPolicy] = None,
) -> T:
    """异步重试：退避用 asyncio.sleep，不堵事件循环。"""
    policy = policy or RetryPolicy(backoff=BackoffPolicy())
    breaker: Optional[CircuitBreaker] = None
    if policy.use_circuit_breaker:
        breaker = get_circuit_registry().get(dependency)

    last_exc: Optional[BaseException] = None
    metrics = get_metrics()

    for attempt in range(1, policy.max_attempts + 1):
        if breaker is not None:
            breaker.before_call()

        span = get_tracer().current
        t0 = time.time()
        try:
            outcome = fn()
            if asyncio.iscoroutine(outcome) or isinstance(outcome, Awaitable):
                result = await outcome  # type: ignore[misc]
            else:
                result = outcome  # type: ignore[assignment]
            latency_ms = (time.time() - t0) * 1000
            if breaker is not None:
                breaker.on_success()
            metrics.incr("call_success_total", dependency=dependency)
            metrics.observe("call_latency_ms", latency_ms, dependency=dependency)
            if span:
                span.add_event(
                    "call_ok",
                    dependency=dependency,
                    attempt=attempt,
                    latency_ms=round(latency_ms, 2),
                )
            if attempt > 1:
                metrics.incr("call_recovered_total", dependency=dependency)
            return result  # type: ignore[return-value]
        except CircuitOpenError:
            raise
        except policy.retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            latency_ms = (time.time() - t0) * 1000
            err_name = type(exc).__name__
            if breaker is not None:
                breaker.on_failure()
            metrics.incr(
                "call_error_total", dependency=dependency, error=err_name
            )
            logger.warning(
                "调用失败 dependency=%s attempt=%s/%s error=%s: %s",
                dependency,
                attempt,
                policy.max_attempts,
                err_name,
                exc,
            )
            if span:
                span.add_event(
                    "call_attempt_failed",
                    dependency=dependency,
                    attempt=attempt,
                    error_class=err_name,
                    latency_ms=round(latency_ms, 2),
                )

            if attempt >= policy.max_attempts:
                break

            if policy.backoff is not None:
                sleep_ms = compute_backoff_ms(attempt, policy.backoff)
                metrics.observe("backoff_ms", sleep_ms, dependency=dependency)
                logger.info(
                    "退避等待 dependency=%s backoff_ms=%.0f",
                    dependency,
                    sleep_ms,
                )
                if span:
                    span.add_event(
                        "backoff",
                        dependency=dependency,
                        attempt=attempt,
                        backoff_ms=round(sleep_ms, 2),
                    )
                await asyncio.sleep(sleep_ms / 1000.0)

    assert last_exc is not None
    metrics.incr("call_final_failure_total", dependency=dependency)
    raise last_exc
