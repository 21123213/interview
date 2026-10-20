"""用户模型和数据库操作"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.database import query, execute, escape_sql_string, build_insert_sql, build_update_sql


class UserModel:
    """用户数据操作类"""
    
    @staticmethod
    def create_user(username: str, password_hash: str, phone: str) -> int:
        """创建用户"""
        sql = build_insert_sql('users', {
            'username': username,
            'password_hash': password_hash,
            'phone': phone,
            'is_active': 1
        })
        result = execute(sql)
        return result['last_insert_id']
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        sql = f"SELECT * FROM users WHERE username = {escape_sql_string(username)}"
        results = query(sql)
        return results[0] if results else None
    
    @staticmethod
    def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
        """根据手机号获取用户"""
        sql = f"SELECT * FROM users WHERE phone = {escape_sql_string(phone)}"
        results = query(sql)
        return results[0] if results else None
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        sql = f"SELECT * FROM users WHERE id = {escape_sql_string(user_id)}"
        results = query(sql)
        return results[0] if results else None
    
    @staticmethod
    def username_exists(username: str) -> bool:
        """检查用户名是否存在"""
        sql = f"SELECT COUNT(*) as count FROM users WHERE username = {escape_sql_string(username)}"
        results = query(sql)
        return results[0]['count'] > 0 if results else False
    
    @staticmethod
    def phone_exists(phone: str) -> bool:
        """检查手机号是否存在"""
        sql = f"SELECT COUNT(*) as count FROM users WHERE phone = {escape_sql_string(phone)}"
        results = query(sql)
        return results[0]['count'] > 0 if results else False


class VerificationCodeModel:
    """验证码数据操作类"""
    
    @staticmethod
    def create_code(phone: str, code: str, expire_minutes: int = 5) -> int:
        """创建验证码"""
        expires_at = datetime.now() + timedelta(minutes=expire_minutes)
        sql = build_insert_sql('verification_codes', {
            'phone': phone,
            'code': code,
            'expires_at': expires_at,
            'used': 0
        })
        result = execute(sql)
        return result['last_insert_id']
    
    @staticmethod
    def verify_code(phone: str, code: str) -> bool:
        """验证验证码"""
        # 查询最新的未使用的验证码
        sql = f"""
            SELECT * FROM verification_codes
            WHERE phone = {escape_sql_string(phone)} 
            AND code = {escape_sql_string(code)} 
            AND used = 0
            AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
        """
        results = query(sql)
        
        if not results:
            return False
        
        # 标记为已使用
        code_id = results[0]['id']
        update_sql = build_update_sql('verification_codes', {'used': 1}, {'id': code_id})
        execute(update_sql)
        
        return True
    
    @staticmethod
    def clean_expired_codes():
        """清理过期的验证码"""
        sql = "DELETE FROM verification_codes WHERE expires_at < NOW()"
        execute(sql)
