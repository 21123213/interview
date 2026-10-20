"""
WebSocket API - 实时进度推送
用于文件处理进度的实时通知
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set
import asyncio
import json
from app.core.security import get_current_user_from_token
from app.core.redis_manager import redis_manager
from app.models.file import FileMetadataModel

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # {file_id: Set[WebSocket连接]}
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # {websocket: user_id} 用于权限验证
        self.connection_users: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, file_id: int, user_id: int):
        """
        接受客户端连接
        
        Args:
            websocket: WebSocket连接
            file_id: 监听的文件ID
            user_id: 用户ID
        """
        await websocket.accept()
        
        if file_id not in self.active_connections:
            self.active_connections[file_id] = set()
        
        self.active_connections[file_id].add(websocket)
        self.connection_users[websocket] = user_id
        
        # 只在首次连接或重要时刻打印
        # print(f"✅ WebSocket连接: file_id={file_id}, user_id={user_id}, 当前连接数={len(self.active_connections[file_id])}")
        pass  # 减少日志噪音
    
    def disconnect(self, websocket: WebSocket, file_id: int):
        """断开连接"""
        if file_id in self.active_connections:
            self.active_connections[file_id].discard(websocket)
            
            # 如果该文件没有连接了，删除键
            if not self.active_connections[file_id]:
                del self.active_connections[file_id]
        
        # 清理用户映射
        if websocket in self.connection_users:
            del self.connection_users[websocket]
        
        # print(f"🔌 WebSocket断开: file_id={file_id}")
        pass  # 减少日志噪音
    
    async def send_progress(self, file_id: int, data: dict):
        """
        向监听指定文件的所有客户端发送进度更新
        
        Args:
            file_id: 文件ID
            data: 进度数据 {status, progress, current_step, message}
        """
        if file_id not in self.active_connections:
            return
        
        disconnected = set()
        
        for connection in self.active_connections[file_id]:
            try:
                await connection.send_json(data)
            except Exception as e:
                print(f"⚠️  发送失败: {e}")
                disconnected.add(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn, file_id)
    
    async def broadcast_to_user(self, user_id: int, data: dict):
        """
        向指定用户的所有连接广播消息
        
        Args:
            user_id: 用户ID
            data: 消息数据
        """
        for websocket, uid in self.connection_users.items():
            if uid == user_id:
                try:
                    await websocket.send_json(data)
                except Exception as e:
                    print(f"⚠️  广播失败: {e}")
    
    def get_connection_count(self, file_id: int) -> int:
        """获取指定文件的连接数"""
        return len(self.active_connections.get(file_id, set()))


# 全局连接管理器
manager = ConnectionManager()


@router.websocket("/ws/file/{file_id}/progress")
async def websocket_file_progress(
    websocket: WebSocket,
    file_id: int,
    token: str = Query(...)
):
    """
    WebSocket端点 - 实时文件处理进度
    
    连接URL: ws://localhost:8000/ws/file/{file_id}/progress?token=xxx
    
    Args:
        websocket: WebSocket连接对象
        file_id: 要监听的文件ID
        token: JWT认证token (通过query参数传递)
    
    消息格式:
    {
        "status": "processing",
        "progress": 50,
        "current_step": "chunking",
        "message": "正在切片..."
    }
    """
    try:
        # 验证token并获取用户信息
        try:
            user = await get_current_user_from_token(token)
            user_id = user['id']
        except Exception as e:
            await websocket.close(code=1008, reason="认证失败")
            return
        
        # 验证文件权限
        file_info = FileMetadataModel.get_file_by_id(file_id)
        if not file_info:
            await websocket.close(code=1008, reason="文件不存在")
            return
        
        if file_info['user_id'] != user_id:
            await websocket.close(code=1008, reason="无权访问此文件")
            return
        
        # 接受连接
        await manager.connect(websocket, file_id, user_id)
        
        # 立即发送当前进度
        progress_data = redis_manager.get_task_progress(file_id)
        if progress_data:
            await websocket.send_json(progress_data)
        else:
            # 从数据库获取状态
            await websocket.send_json({
                "status": file_info['status'],
                "progress": 100 if file_info['status'] == 'completed' else 0,
                "current_step": file_info['status'],
                "message": f"文件状态: {file_info['status']}"
            })
        
        # 保持连接，监听客户端消息（心跳包）
        while True:
            try:
                # 接收客户端心跳或命令
                data = await websocket.receive_text()
                
                # 处理客户端命令
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data == "get_progress":
                    # 主动查询进度
                    progress_data = redis_manager.get_task_progress(file_id)
                    if progress_data:
                        await websocket.send_json(progress_data)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"⚠️  WebSocket错误: {e}")
                break
    
    finally:
        manager.disconnect(websocket, file_id)


@router.websocket("/ws/notifications")
async def websocket_user_notifications(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket端点 - 用户通知
    
    连接URL: ws://localhost:8000/ws/notifications?token=xxx
    
    接收用户相关的所有通知:
    - 文件处理完成
    - 系统消息
    - 错误通知
    """
    try:
        # 验证token
        try:
            user = await get_current_user_from_token(token)
            user_id = user['id']
        except Exception as e:
            await websocket.close(code=1008, reason="认证失败")
            return
        
        await websocket.accept()
        
        # 发送欢迎消息
        await websocket.send_json({
            "type": "welcome",
            "message": f"欢迎, {user['username']}!",
            "user_id": user_id
        })
        
        # 保持连接
        while True:
            try:
                data = await websocket.receive_text()
                
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                break
    
    finally:
        print(f"🔌 用户通知WebSocket断开: user_id={user_id}")


# ==================== 辅助函数 ====================

async def notify_progress_update(file_id: int, progress_data: dict):
    """
    通知进度更新（从后台任务调用）

    Args:
        file_id: 文件ID
        progress_data: 进度数据
    """
    await manager.send_progress(file_id, progress_data)


def get_active_connections_count() -> dict:
    """获取所有活跃连接统计"""
    return {
        file_id: len(connections)
        for file_id, connections in manager.active_connections.items()
    }


# ==================== 用于后台任务的同步版本 ====================

def broadcast_progress_sync(file_id: int, progress_data: dict):
    """
    同步版本 - 用于在后台任务中调用

    Args:
        file_id: 文件ID
        progress_data: 进度数据
    """
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.send_progress(file_id, progress_data))
        loop.close()
    except Exception as e:
        print(f"⚠️  WebSocket广播失败: {e}")
