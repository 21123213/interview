"""按逻辑角色（fast / strong）路由到具体模型。"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Dict, Optional

from agent.models.base import ChatModel
from agent.models.providers.dashscope import DashScopeChatModel

logger = logging.getLogger("agent.models.router")


class ModelRole(str, Enum):
    """逻辑模型角色，业务代码只依赖角色名，不写死型号。"""

    FAST = "fast"  # 弱/快：分类、简单推理、ReAct 步内默认
    STRONG = "strong"  # 强：复杂规划或升级重试


class ModelRouter:
    """多模型管理：role → ChatModel 实例。"""

    def __init__(self, mapping: Optional[Dict[ModelRole, ChatModel]] = None) -> None:
        self._mapping: Dict[ModelRole, ChatModel] = mapping or {}

    def register(self, role: ModelRole, model: ChatModel) -> None:
        self._mapping[role] = model

    def get(
        self,
        role: ModelRole = ModelRole.FAST,
        *,
        route_reason: str = "default",
    ) -> ChatModel:
        """按角色取模型；不存在则回退 FAST。"""
        model = self._mapping.get(role) or self._mapping.get(ModelRole.FAST)
        if model is None:
            raise RuntimeError(f"未注册任何模型，无法路由 role={role}")
        logger.info(
            "模型路由 role=%s -> %s/%s reason=%s",
            role.value,
            model.provider,
            model.model_id,
            route_reason,
        )
        return model

    def resolve_for_react(
        self,
        *,
        step_index: int,
        force_strong: bool = False,
    ) -> tuple[ChatModel, ModelRole, str]:
        """ReAct 步进时的默认路由策略。

        - 默认用 FAST；
        - force_strong 或步数较深时升级 STRONG（可按需改阈值）。
        """
        if force_strong:
            role = ModelRole.STRONG
            reason = "force_strong"
        elif step_index >= 4 and ModelRole.STRONG in self._mapping:
            role = ModelRole.STRONG
            reason = "deep_step_upgrade"
        else:
            role = ModelRole.FAST
            reason = "react_default"
        return self.get(role, route_reason=reason), role, reason


def get_default_router() -> ModelRouter:
    """从环境变量构建默认路由表（优先 qwen3.8 系列）。"""
    fast_id = (
        os.getenv("AGENT_FAST_MODEL")
        or os.getenv("DASHSCOPE_FAST_MODEL")
        or "qwen3.8-flash"
    )
    strong_id = (
        os.getenv("AGENT_STRONG_MODEL")
        or os.getenv("DASHSCOPE_STRONG_MODEL")
        or os.getenv("DASHSCOPE_ANSWER_MODEL")
        or "qwen3.8-max"
    )
    router = ModelRouter()
    router.register(ModelRole.FAST, DashScopeChatModel(fast_id))
    router.register(ModelRole.STRONG, DashScopeChatModel(strong_id))
    return router
