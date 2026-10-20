"""文件相关的Pydantic模型"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FileMetadataResponse(BaseModel):
    """文件元数据响应模型"""
    id: int
    user_id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    status: str
    chunks_count: int = 0
    error_message: Optional[str] = None
    upload_time: datetime
    processed_time: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: int
    filename: str
    original_filename: str
    file_size: int
    upload_time: datetime
    status: str


class FileListResponse(BaseModel):
    """文件列表响应"""
    total: int
    items: list[FileMetadataResponse]


class FileProcessRequest(BaseModel):
    """文件处理请求"""
    file_id: int = Field(..., description="文件ID")


class FileProcessResponse(BaseModel):
    """文件处理响应"""
    file_id: int
    status: str
    message: str
    chunks_count: Optional[int] = None


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    file_ids: list[int] = Field(..., min_length=1, description="要删除的文件 ID 列表")


class BatchDeleteResponse(BaseModel):
    """批量删除结果"""
    success: bool = True
    deleted: int = 0
    failed: int = 0
    message: str = ''
    errors: list[str] = Field(default_factory=list)
