"""文件模型和数据库操作"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.database import query, execute, escape_sql_string, build_insert_sql, build_update_sql


class FileMetadataModel:
    """文件元数据操作类"""
    
    @staticmethod
    def create_file_metadata(
        user_id: int,
        filename: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        file_type: str,
        mime_type: str
    ) -> int:
        """创建文件元数据记录"""
        sql = build_insert_sql('file_metadata', {
            'user_id': user_id,
            'filename': filename,
            'original_filename': original_filename,
            'file_path': file_path,
            'file_size': file_size,
            'file_type': file_type,
            'mime_type': mime_type,
            'status': 'pending'
        })
        result = execute(sql)
        return result['last_insert_id']
    
    @staticmethod
    def get_file_by_id(file_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取文件元数据"""
        sql = f"SELECT * FROM file_metadata WHERE id = {escape_sql_string(file_id)}"
        results = query(sql)
        return results[0] if results else None
    
    @staticmethod
    def get_files_by_user(user_id: int, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        """获取用户的文件列表（分页）"""
        offset = (page - 1) * size
        sql = f"""SELECT * FROM file_metadata WHERE user_id = {escape_sql_string(user_id)} ORDER BY upload_time DESC"""
        return query(sql)
    
    @staticmethod
    def count_user_files(user_id: int) -> int:
        """统计用户文件数量"""
        sql = f"SELECT COUNT(*) as count FROM file_metadata WHERE user_id = {escape_sql_string(user_id)}"
        results = query(sql)
        return results[0]['count'] if results else 0
    
    @staticmethod
    def update_file_status(
        file_id: int,
        status: str,
        chunks_count: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """更新文件处理状态"""
        if chunks_count is not None:
            data = {
                'status': status,
                'chunks_count': chunks_count,
                'error_message': error_message,
                'processed_time': 'NOW()'
            }
        else:
            data = {
                'status': status,
                'error_message': error_message
            }
        
        # 手动构建，因为 NOW() 不需要引号
        set_parts = []
        for k, v in data.items():
            if v == 'NOW()':
                set_parts.append(f'{k} = NOW()')
            else:
                set_parts.append(f'{k} = {escape_sql_string(v)}')
        
        sql = f"UPDATE file_metadata SET {', '.join(set_parts)} WHERE id = {escape_sql_string(file_id)}"
        execute(sql)
    
    @staticmethod
    def update_field(file_id: int, field_name: str, value: Any):
        """更新文件的单个字段"""
        import json
        
        # 如果是字典，转换为JSON字符串
        if isinstance(value, dict):
            value = json.dumps(value)
        
        sql = f"UPDATE file_metadata SET {field_name} = {escape_sql_string(value)} WHERE id = {escape_sql_string(file_id)}"
        execute(sql)
    
    @staticmethod
    def delete_file(file_id: int):
        """删除文件元数据（级联删除内容）"""
        sql = f"DELETE FROM file_metadata WHERE id = {escape_sql_string(file_id)}"
        execute(sql)


class FileContentModel:
    """文件内容操作类"""
    
    @staticmethod
    def save_file_content(file_id: int, content: bytes) -> int:
        """保存文件二进制内容"""
        # 注意：二进制内容需要特殊处理，这里假设 API 支持
        sql = build_insert_sql('file_content', {
            'file_id': file_id,
            'content': content
        })
        result = execute(sql)
        return result['last_insert_id']
    
    @staticmethod
    def get_file_content(file_id: int) -> Optional[bytes]:
        """获取文件二进制内容"""
        sql = f"SELECT content FROM file_content WHERE file_id = {escape_sql_string(file_id)}"
        results = query(sql)
        return results[0]['content'] if results else None
    
    @staticmethod
    def delete_file_content(file_id: int):
        """删除文件内容"""
        sql = f"DELETE FROM file_content WHERE file_id = {escape_sql_string(file_id)}"
        execute(sql)
