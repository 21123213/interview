"""对话相关的Pydantic模型"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatQueryRequest(BaseModel):
    """对话查询请求"""
    query: str = Field(..., min_length=1, max_length=1000, description="用户查询")
    session_id: Optional[str] = None
    file_ids: Optional[List[int]] = Field(
        None,
        description="限定检索的文件 ID 列表；为空则检索用户全部已处理文档",
    )
    vector_weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="向量（语义）融合权重；与 bm25_weight 会归一化到和为 1；不传则用服务端默认",
    )
    bm25_weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="BM25（关键词）融合权重；不传则用 1-vector_weight 或服务端默认",
    )


class ChatSource(BaseModel):
    """对话来源文档"""
    content: str
    score: float
    metadata: Optional[dict] = None


class ChatQueryResponse(BaseModel):
    """对话查询响应"""
    answer: str
    sources: List[ChatSource] = []
    session_id: str


class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # user 或 assistant
    content: str
    timestamp: datetime
    sources: Optional[List[ChatSource]] = None


class ChatHistoryResponse(BaseModel):
    """对话历史响应"""
    session_id: str
    messages: List[ChatMessage]


class ChatSessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None


class ChatSessionListResponse(BaseModel):
    """会话列表响应"""
    total: int
    sessions: List[ChatSessionResponse]
