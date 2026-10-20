"""单轮 Agent 资源预算（ReAct / Plan-Execute 共用）。

与步数类上限互补，不可互相替代：
- ReAct 的 max_steps / PE 的 max_replans：限制「推理轮次」次数
- 本模块：限制「本轮累计 prompt token」与「web_search 调用次数」

触顶后由各自 loop 强制综合已有结果作答（禁止继续搜），
避免无限搜索烧钱。环境变量见 load_run_budget_config。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class RunBudgetConfig:
    """一次用户提问（含多步工具循环）的预算配置。"""

    # 本轮累计 prompt_tokens 硬上限（API 回传累加，近似即可）
    token_budget: int = 80000
    # 软阈值比例：达到后提示模型停止搜索，但仍允许工具
    soft_ratio: float = 0.75
    # 硬阈值比例：达到后禁止工具，强制综合答案
    hard_ratio: float = 0.90
    # 单轮允许的 web_search 调用次数上限（每次 function call 计 1）
    web_search_max: int = 8

    @property
    def soft_tokens(self) -> int:
        return max(1, int(self.token_budget * self.soft_ratio))

    @property
    def hard_tokens(self) -> int:
        return max(1, int(self.token_budget * self.hard_ratio))


def load_run_budget_config() -> RunBudgetConfig:
    """从环境变量加载；未设置则用旅游场景默认值。"""
    return RunBudgetConfig(
        token_budget=_env_int("AGENT_RUN_TOKEN_BUDGET", 80000),
        soft_ratio=_env_float("AGENT_RUN_TOKEN_SOFT_RATIO", 0.60),
        hard_ratio=_env_float("AGENT_RUN_TOKEN_HARD_RATIO", 0.85),
        web_search_max=_env_int("AGENT_WEB_SEARCH_MAX_PER_RUN", 8),
    )


@dataclass
class RunBudgetState:
    """一次用户提问内的累计（跨 ReAct step / PE round，不跨下一问）。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    web_search_calls: int = 0
    soft_nudged: bool = False

    def add_llm_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens += max(0, int(prompt_tokens or 0))
        self.completion_tokens += max(0, int(completion_tokens or 0))

    def add_web_search(self, n: int = 1) -> None:
        self.web_search_calls += max(0, int(n or 0))

    def snapshot(self, cfg: RunBudgetConfig) -> dict:
        """写入 transcript / pending，便于对照成本与 resume 恢复。"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "web_search_calls": self.web_search_calls,
            "soft_nudged": self.soft_nudged,
            "token_budget": cfg.token_budget,
            "soft_tokens": cfg.soft_tokens,
            "hard_tokens": cfg.hard_tokens,
            "web_search_max": cfg.web_search_max,
        }
