"""Agent 薄接口请求模型（不写 RAG 会话表）。"""
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field


AgentRunMode = Literal["react", "plan_execute"]


class AgentQueryRequest(BaseModel):
    """Agent 查询 / 流式运行。"""

    query: str = Field(..., min_length=1, max_length=4000, description="用户输入")
    session_id: Optional[str] = Field(
        None, description="Agent 会话 ID（进程内记忆）；不传则新建"
    )
    mode: AgentRunMode = Field(
        "react",
        description="运行模式：react | plan_execute",
    )
    resume_token: Optional[str] = Field(
        None,
        description="若上一轮 needs_input，带上此 token 表示本轮为补参恢复",
    )
    answers: Optional[Union[str, Dict[str, Any]]] = Field(
        None,
        description="补参内容；与 resume_token 一起使用时优先走 resume",
    )
