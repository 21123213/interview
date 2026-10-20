"""
聊天会话和消息模型
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.database import execute_query, fetch_one, fetch_all


class ChatSessionModel:
    """聊天会话模型"""
    
    @staticmethod
    def create_session(session_id: str, user_id: int, title: str = "新会话") -> int:
        """创建新会话"""
        sql = """
        INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        now = datetime.now()
        result = execute_query(sql, (session_id, user_id, title, now, now))
        return result
    
    @staticmethod
    def get_session_by_id(session_id: str) -> Optional[Dict]:
        """根据session_id获取会话"""
        sql = """
        SELECT id, session_id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE session_id = %s
        """
        
        row = fetch_one(sql, (session_id,))
        
        if row:
            return {
                'id': row[0],
                'session_id': row[1],
                'user_id': row[2],
                'title': row[3],
                'created_at': row[4].isoformat() if row[4] else None,
                'updated_at': row[5].isoformat() if row[5] else None
            }
        
        return None
    
    @staticmethod
    def get_or_create_session(session_id: str, user_id: int) -> Dict:
        """获取或创建会话"""
        session = ChatSessionModel.get_session_by_id(session_id)
        
        if not session:
            ChatSessionModel.create_session(session_id, user_id)
            session = ChatSessionModel.get_session_by_id(session_id)
        
        return session
    
    @staticmethod
    def get_user_sessions(user_id: int, limit: int = 20) -> List[Dict]:
        """获取用户的所有会话"""
        sql = """
        SELECT s.id, s.session_id, s.user_id, s.title, s.created_at, s.updated_at,
               (SELECT content FROM chat_messages 
                WHERE session_id = s.session_id 
                ORDER BY created_at DESC LIMIT 1) as last_message
        FROM chat_sessions s
        WHERE s.user_id = %s
        ORDER BY s.updated_at DESC
        LIMIT %s
        """
        
        rows = fetch_all(sql, (user_id, limit))
        
        sessions = []
        for row in rows:
            sessions.append({
                'id': row[0],
                'session_id': row[1],
                'user_id': row[2],
                'title': row[3],
                'created_at': row[4].isoformat() if row[4] else None,
                'updated_at': row[5].isoformat() if row[5] else None,
                'last_message': row[6]
            })
        
        return sessions
    
    @staticmethod
    def update_session_title(session_id: str, title: str):
        """更新会话标题"""
        sql = """
        UPDATE chat_sessions
        SET title = %s, updated_at = %s
        WHERE session_id = %s
        """
        
        execute_query(sql, (title, datetime.now(), session_id))
    
    @staticmethod
    def update_session_timestamp(session_id: str):
        """更新会话时间戳"""
        sql = """
        UPDATE chat_sessions
        SET updated_at = %s
        WHERE session_id = %s
        """
        
        execute_query(sql, (datetime.now(), session_id))

    @staticmethod
    def update_session_time(session_id: str):
        """别名，兼容旧调用"""
        ChatSessionModel.update_session_timestamp(session_id)
    
    @staticmethod
    def delete_session(session_id: str):
        """删除会话 (级联删除消息)"""
        sql = "DELETE FROM chat_sessions WHERE session_id = %s"
        execute_query(sql, (session_id,))


class ChatMessageModel:
    """聊天消息模型"""
    
    @staticmethod
    def create_message(
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[Dict]] = None
    ) -> int:
        """创建消息记录"""
        sql = """
        INSERT INTO chat_messages (session_id, role, content, sources, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        sources_json = json.dumps(sources) if sources else None
        result = execute_query(sql, (session_id, role, content, sources_json, datetime.now()))
        
        # 更新会话时间戳
        ChatSessionModel.update_session_timestamp(session_id)
        
        return result
    
    @staticmethod
    def get_session_messages(
        session_id: str,
        roles: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取会话的消息列表
        
        Args:
            session_id: 会话ID
            roles: 角色过滤 (如 ['user', 'assistant'])
            limit: 限制数量
        """
        if roles:
            placeholders = ','.join(['%s'] * len(roles))
            sql = f"""
            SELECT id, session_id, role, content, sources, created_at
            FROM chat_messages
            WHERE session_id = %s AND role IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT %s
            """
            params = [session_id] + roles + [limit]
        else:
            sql = """
            SELECT id, session_id, role, content, sources, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """
            params = [session_id, limit]
        
        rows = fetch_all(sql, tuple(params))
        
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'session_id': row[1],
                'role': row[2],
                'content': row[3],
                'sources': json.loads(row[4]) if row[4] else None,
                'created_at': row[5].isoformat() if row[5] else None
            })
        
        # 反转顺序 (从旧到新)
        messages.reverse()
        
        return messages
    
    @staticmethod
    def get_recent_messages(
        session_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """获取最近的消息 (只包含user和assistant)"""
        return ChatMessageModel.get_session_messages(
            session_id,
            roles=['user', 'assistant'],
            limit=limit
        )
    
    @staticmethod
    def count_session_messages(session_id: str) -> int:
        """统计会话消息数量"""
        sql = "SELECT COUNT(*) FROM chat_messages WHERE session_id = %s"
        row = fetch_one(sql, (session_id,))
        return row[0] if row else 0
