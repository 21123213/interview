"""用户相关的Pydantic模型"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import re


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")


class UserCreate(UserBase):
    """用户注册模型"""
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str = Field(..., pattern=r'^1[3-9]\d{9}$', description="手机号")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")
    
    @field_validator('phone')
    def validate_phone(cls, v):
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v


class UserLogin(BaseModel):
    """用户登录模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    phone: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT Token模型"""
    access_token: str
    token_type: str = "bearer"
    user_info: UserResponse


class TokenData(BaseModel):
    """Token数据模型"""
    user_id: Optional[int] = None
    username: Optional[str] = None


class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    phone: str = Field(..., pattern=r'^1[3-9]\d{9}$', description="手机号")


class VerifyCodeRequest(BaseModel):
    """验证验证码请求"""
    phone: str = Field(..., pattern=r'^1[3-9]\d{9}$', description="手机号")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")


class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool = True
    message: str
    data: Optional[dict] = None
