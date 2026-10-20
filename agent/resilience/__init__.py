"""韧性层：指数退避、熔断、统一重试。

重要约定：
- 重试 / 熔断细节只写入观测（日志、span、metrics）。
- 对外（给主 Agent / 调用方）只返回最终成功结果或最终异常，
  不在返回值里附带 attempt 列表，避免污染 ReAct Observation。
"""

from agent.resilience.backoff import BackoffPolicy, compute_backoff_ms
from agent.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
    get_circuit_registry,
)
from agent.resilience.retry import RetryPolicy, call_with_retry, call_with_retry_async

__all__ = [
    "BackoffPolicy",
    "compute_backoff_ms",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitOpenError",
    "CircuitState",
    "get_circuit_registry",
    "RetryPolicy",
    "call_with_retry",
    "call_with_retry_async",
]
