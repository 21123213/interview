"""认证相关API"""
import os
from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, Token,
    SendCodeRequest, VerifyCodeRequest, MessageResponse
)
from app.models.user import UserModel, VerificationCodeModel
from app.core.security import (
    get_password_hash, authenticate_user, 
    create_access_token, get_current_user
)
from app.core.sms import pnvs_service
from app.utils.helpers import mask_phone

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/send-code", response_model=MessageResponse)
async def send_verification_code(request: SendCodeRequest):
    """发送短信验证码（使用 PNVS 服务）"""
    phone = request.phone
    
    # 检查手机号是否已注册
    if UserModel.phone_exists(phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该手机号已注册"
        )
    
    # 检查 PNVS 服务是否初始化
    if not pnvs_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="短信服务未初始化，请检查配置"
        )
    
    # 使用 PNVS 发送验证码
    result = pnvs_service.send_verification_code(
        phone=phone,
        valid_time=5,  # 5分钟有效期
        out_id=f"register_{phone}"  # 外部流水号
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"验证码发送失败: {result['message']}"
        )
    
    # 测试模式下保存验证码到数据库（生产模式由阿里云托管，无需保存）
    if pnvs_service.debug_mode and result.get('code'):
        VerificationCodeModel.create_code(phone, result['code'], 5)
    
    # 返回成功信息
    debug_hint = f" (测试模式: {result['code']})" if result.get('code') else ""
    
    return MessageResponse(
        success=True,
        message=f"验证码已发送到 {mask_phone(phone)}{debug_hint}",
        data={
            "expire_time": 300,  # 5分钟
            "biz_id": result.get('biz_id'),
            "debug_code": result.get('code')  # 仅测试模式返回
        }
    )


@router.post("/verify-code", response_model=MessageResponse)
async def verify_code(request: VerifyCodeRequest):
    """验证验证码（不实际使用，仅供前端验证）"""
    phone = request.phone
    code = request.code
    
    # 验证验证码
    is_valid = VerificationCodeModel.verify_code(phone, code)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )
    
    return MessageResponse(
        success=True,
        message="验证码验证成功",
        data={"valid": True}
    )


@router.post("/register", response_model=MessageResponse)
async def register(user: UserCreate):
    """用户注册"""
    # 检查用户名是否存在
    if UserModel.username_exists(user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查手机号是否存在
    if UserModel.phone_exists(user.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已注册"
        )
    
    # 使用 PNVS 托管验证（生产模式）或数据库验证（测试模式）
    if pnvs_service:
        if pnvs_service.debug_mode:
            # 测试模式不验证
            pass
        else:
            # 生产模式：使用 PNVS 托管验证
            verify_result = pnvs_service.verify_code(
                phone=user.phone,
                code=user.code,
                out_id=f"register_{user.phone}"
            )
            
            if not verify_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=verify_result['message']
                )
    else:
        # PNVS 服务未初始化，降级到数据库验证
        if not VerificationCodeModel.verify_code(user.phone, user.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误或已过期"
            )
    
    # 创建用户
    password_hash = get_password_hash(user.password)
    user_id = UserModel.create_user(user.username, password_hash, user.phone)
    
    return MessageResponse(
        success=True,
        message="注册成功",
        data={"user_id": user_id, "username": user.username}
    )


@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    """用户登录"""
    # 认证用户
    db_user = authenticate_user(user.username, user.password)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建JWT Token
    access_token = create_access_token(
        data={"user_id": db_user['id'], "username": db_user['username']}
    )
    
    # 构造用户响应
    user_response = UserResponse(
        id=db_user['id'],
        username=db_user['username'],
        phone=mask_phone(db_user['phone']),
        is_active=db_user['is_active'],
        created_at=db_user['created_at']
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_info=user_response
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserResponse(
        id=current_user['id'],
        username=current_user['username'],
        phone=mask_phone(current_user['phone']),
        is_active=current_user['is_active'],
        created_at=current_user['created_at']
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: dict = Depends(get_current_user)):
    """登出（客户端清除Token即可）"""
    return MessageResponse(
        success=True,
        message="登出成功"
    )
