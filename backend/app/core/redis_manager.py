"""
Redis 缓存管理服务

本模块只管：
- session:{id}:context      多轮对话窗口（清会话只清这个）
- file:{id}:progress        上传异步进度
- lock:file:{id}:processing 防重复处理锁
- user:{id}:files           文件列表短缓存

不要在这里清 / 写 RAG 答案缓存。答案缓存在 app.core.qa_cache，
前缀为 rag:qa: 与 user:{id}:corpus_ver，与会话窗口隔离。
"""
import os
import json
import redis
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class RedisManager:
    """Redis缓存管理类"""
    
    def __init__(self):
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', '6379'))
        self.db = int(os.getenv('REDIS_DB', '0'))
        self.password = os.getenv('REDIS_PASSWORD', None) or None
        
        # 创建Redis客户端
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=True,
            socket_connect_timeout=5
        )
        
        # 测试连接
        try:
            self.client.ping()
            print(f"✅ Redis连接成功: {self.host}:{self.port}")
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
            raise
    
    # ==================== 会话上下文管理 ====================
    
    def save_session_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        sources: Optional[List[Dict]] = None
    ):
        """
        保存会话消息到缓存
        
        Args:
            session_id: 会话ID
            role: 角色 (user/assistant/system)
            content: 消息内容
            sources: 来源信息(可选)
        """
        key = f"session:{session_id}:context"
        
        # 获取现有上下文
        context = self.get_session_context(session_id)
        
        # 添加新消息
        message = {
            "role": role,
            "content": content,
            "timestamp": self._get_timestamp()
        }
        if sources:
            message["sources"] = sources
        
        context.append(message)

        # 最近 N 轮完整问答；总 token 超限则压缩
        from app.core.session_memory import enforce_memory_limits
        context = enforce_memory_limits(context)

        # 保存到Redis (TTL: 30分钟)
        ttl = int(os.getenv('CONTEXT_CACHE_TTL', '1800'))
        self.client.setex(
            key,
            ttl,
            json.dumps(context, ensure_ascii=False)
        )
    
    def get_session_context(self, session_id: str) -> List[Dict]:
        """
        获取会话上下文
        
        Returns:
            消息列表 [{"role": "user", "content": "...", "timestamp": "..."}, ...]
        """
        key = f"session:{session_id}:context"
        cached = self.client.get(key)
        
        if cached:
            try:
                return json.loads(cached)
            except:
                return []
        
        return []
    
    def clear_session_context(self, session_id: str):
        """清除会话上下文"""
        key = f"session:{session_id}:context"
        self.client.delete(key)
    
    # ==================== 任务进度管理 ====================
    
    def set_task_progress(
        self,
        file_id: int,
        status: str,
        progress: int,
        current_step: str,
        message: str,
        processed_chunks: int = None
    ):
        """
        设置文件处理进度
        
        Args:
            file_id: 文件ID
            status: 状态 (pending/processing/completed/failed)
            progress: 进度百分比 (0-100)
            current_step: 当前步骤 (parsing/chunking/embedding)
            message: 进度消息
            processed_chunks: 已处理的chunks数量(可选)
        """
        key = f"file:{file_id}:progress"
        
        data = {
            "status": status,
            "progress": progress,
            "current_step": current_step,
            "message": message,
            "updated_at": self._get_timestamp()
        }
        
        if processed_chunks is not None:
            data["processed_chunks"] = processed_chunks
        
        # 使用Hash存储，方便单独更新字段
        for field, value in data.items():
            self.client.hset(key, field, value)
        
        # 设置过期时间 (1小时)
        self.client.expire(key, 3600)
    
    def get_task_progress(self, file_id: int) -> Optional[Dict[str, Any]]:
        """获取文件处理进度"""
        key = f"file:{file_id}:progress"
        data = self.client.hgetall(key)
        
        if data:
            # 转换progress为整数
            if 'progress' in data:
                data['progress'] = int(data['progress'])
            return data
        
        return None
    
    def clear_task_progress(self, file_id: int):
        """清除任务进度缓存"""
        key = f"file:{file_id}:progress"
        self.client.delete(key)
    
    # ==================== 文件处理锁 ====================
    
    def acquire_file_lock(self, file_id: int, task_id: str, ttl: int = 600) -> bool:
        """
        获取文件处理锁（防止重复处理）
        
        Args:
            file_id: 文件ID
            task_id: 任务ID
            ttl: 锁过期时间(秒)，默认10分钟
        
        Returns:
            是否成功获取锁
        """
        key = f"lock:file:{file_id}:processing"
        
        # SET NX: 只在key不存在时设置
        acquired = self.client.set(
            key,
            task_id,
            nx=True,  # Not eXists
            ex=ttl    # EXpire
        )
        
        return acquired is not None
    
    def release_file_lock(self, file_id: int):
        """释放文件处理锁"""
        key = f"lock:file:{file_id}:processing"
        self.client.delete(key)
    
    def get_file_lock_owner(self, file_id: int) -> Optional[str]:
        """获取文件锁的持有者（任务ID）"""
        key = f"lock:file:{file_id}:processing"
        return self.client.get(key)
    
    # ==================== 用户文件列表缓存 ====================
    
    def cache_user_files(self, user_id: int, files: List[Dict], ttl: int = 300):
        """
        缓存用户文件列表
        
        Args:
            user_id: 用户ID
            files: 文件列表
            ttl: 过期时间(秒)，默认5分钟
        """
        key = f"user:{user_id}:files"
        self.client.setex(
            key,
            ttl,
            json.dumps(files, ensure_ascii=False, default=str)
        )
    
    def get_cached_user_files(self, user_id: int) -> Optional[List[Dict]]:
        """获取缓存的用户文件列表"""
        key = f"user:{user_id}:files"
        cached = self.client.get(key)
        
        if cached:
            try:
                return json.loads(cached)
            except:
                return None
        
        return None
    
    def invalidate_user_files_cache(self, user_id: int):
        """使用户文件列表缓存失效"""
        key = f"user:{user_id}:files"
        self.client.delete(key)
    
    # ==================== 通用缓存 ====================
    # 说明：已移除 query_history（从未接入主链路）。
    # RAG 答案缓存见 app.core.qa_cache（前缀 rag:qa:，与 session:* 分离）。
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        
        if ttl:
            self.client.setex(key, ttl, value)
        else:
            self.client.set(key, value)
    
    def get(self, key: str, as_json: bool = False) -> Any:
        """获取缓存"""
        value = self.client.get(key)
        
        if value and as_json:
            try:
                return json.loads(value)
            except:
                return value
        
        return value
    
    def delete(self, key: str):
        """删除缓存"""
        self.client.delete(key)
    
    def exists(self, key: str) -> bool:
        """检查key是否存在"""
        return self.client.exists(key) > 0
    
    # ==================== 工具方法 ====================
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳字符串"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def ping(self) -> bool:
        """测试连接"""
        try:
            return self.client.ping()
        except:
            return False
    
    def flush_all(self):
        """清空所有缓存（慎用！）"""
        self.client.flushdb()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取Redis统计信息"""
        info = self.client.info()
        return {
            "version": info['redis_version'],
            "used_memory": info['used_memory_human'],
            "connected_clients": info['connected_clients'],
            "total_keys": self.client.dbsize()
        }


# 全局单例
redis_manager = RedisManager()


# 测试函数
def test_redis():
    """测试Redis服务"""
    print("\n" + "=" * 50)
    print("测试Redis服务")
    print("=" * 50)
    
    # 1. 测试基本读写
    redis_manager.set("test_key", "test_value", ttl=60)
    value = redis_manager.get("test_key")
    assert value == "test_value", "基本读写测试失败"
    print("✅ 基本读写测试通过")
    
    # 2. 测试会话上下文
    redis_manager.save_session_message(
        session_id="test_session",
        role="user",
        content="你好"
    )
    redis_manager.save_session_message(
        session_id="test_session",
        role="assistant",
        content="你好！有什么可以帮助你的？"
    )
    context = redis_manager.get_session_context("test_session")
    assert len(context) == 2, "会话上下文测试失败"
    print(f"✅ 会话上下文测试通过: {len(context)} 条消息")
    
    # 3. 测试任务进度
    redis_manager.set_task_progress(
        file_id=123,
        status="processing",
        progress=50,
        current_step="chunking",
        message="正在切片..."
    )
    progress = redis_manager.get_task_progress(123)
    assert progress['progress'] == 50, "任务进度测试失败"
    print(f"✅ 任务进度测试通过: {progress['message']}")
    
    # 4. 测试文件锁
    acquired = redis_manager.acquire_file_lock(456, "task_001")
    assert acquired, "文件锁获取失败"
    
    acquired_again = redis_manager.acquire_file_lock(456, "task_002")
    assert not acquired_again, "文件锁重复获取应该失败"
    
    redis_manager.release_file_lock(456)
    print("✅ 文件锁测试通过")
    
    # 5. 获取统计信息
    stats = redis_manager.get_stats()
    print(f"✅ Redis统计: {stats['total_keys']} 个key, 内存: {stats['used_memory']}")
    
    # 清理测试数据
    redis_manager.delete("test_key")
    redis_manager.clear_session_context("test_session")
    redis_manager.clear_task_progress(123)
    
    print("\n✅ 所有测试通过!")


if __name__ == "__main__":
    test_redis()
