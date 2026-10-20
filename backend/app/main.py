"""FastAPI主应用"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 必须在导入会拉取 huggingface_hub 的模块之前加载 .env
# HF_ENDPOINT 在 huggingface_hub.constants 导入时就会固化
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()  # 兼容 cwd 下的 .env

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# backend 根目录（导入 app.*）；仓库根目录（导入 agent.*）
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.api import auth_router, file_router, chat_router, agent_router
from app.api.websocket import router as websocket_router

# 创建FastAPI应用
app = FastAPI(
    title=os.getenv('APP_NAME', 'RAG System'),
    version=os.getenv('APP_VERSION', '1.0.0'),
    description="RAG智能助手后端API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(file_router)
app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(websocket_router, tags=["WebSocket"])  # ← WebSocket路由


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "RAG System API",
        "version": os.getenv('APP_VERSION', '1.0.0'),
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "rag-system"
    }


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    debug = os.getenv('APP_DEBUG', 'False').lower() == 'true'
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "服务器内部错误",
            "detail": str(exc) if debug else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv('APP_HOST', '0.0.0.0')
    port = int(os.getenv('APP_PORT', '8000'))
    debug = os.getenv('APP_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting server at http://{host}:{port}")
    print(f"API Docs: http://{host}:{port}/docs")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug
    )
