"""
文档元素和切片模型
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.database import execute_query, fetch_one, fetch_all


class DocumentElementModel:
    """文档元素模型 - 存储Unstructured解析的原始元素"""
    
    @staticmethod
    def create_element(
        file_id: int,
        element_index: int,
        element_type: str,
        text_content: str,
        metadata: Dict[str, Any]
    ) -> int:
        """创建文档元素记录"""
        sql = """
        INSERT INTO document_elements 
        (file_id, element_index, element_type, text_content, metadata)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        result = execute_query(
            sql,
            (file_id, element_index, element_type, text_content, json.dumps(metadata))
        )
        
        return result
    
    @staticmethod
    def get_elements_by_file(file_id: int) -> List[Dict]:
        """获取文件的所有元素"""
        sql = """
        SELECT id, file_id, element_index, element_type, text_content, metadata, created_at
        FROM document_elements
        WHERE file_id = %s
        ORDER BY element_index
        """
        
        rows = fetch_all(sql, (file_id,))
        
        elements = []
        for row in rows:
            elements.append({
                'id': row[0],
                'file_id': row[1],
                'element_index': row[2],
                'element_type': row[3],
                'text_content': row[4],
                'metadata': json.loads(row[5]) if row[5] else {},
                'created_at': row[6].isoformat() if row[6] else None
            })
        
        return elements
    
    @staticmethod
    def get_elements_by_type(file_id: int, element_type: str) -> List[Dict]:
        """获取文件中指定类型的元素"""
        sql = """
        SELECT id, element_index, text_content, metadata
        FROM document_elements
        WHERE file_id = %s AND element_type = %s
        ORDER BY element_index
        """
        
        rows = fetch_all(sql, (file_id, element_type))
        
        elements = []
        for row in rows:
            elements.append({
                'id': row[0],
                'element_index': row[1],
                'text_content': row[2],
                'metadata': json.loads(row[3]) if row[3] else {}
            })
        
        return elements
    
    @staticmethod
    def count_by_file(file_id: int) -> int:
        """统计文件的元素数量"""
        sql = "SELECT COUNT(*) FROM document_elements WHERE file_id = %s"
        row = fetch_one(sql, (file_id,))
        return row[0] if row else 0


class DocumentChunkModel:
    """文档切片模型 - 存储组合后的切片"""
    
    @staticmethod
    def create_chunk(
        file_id: int,
        chunk_index: int,
        chunk_text: str,
        char_count: int,
        element_count: int,
        element_ids: List[int],
        page_numbers: List[int],
        content_types: Optional[List[str]] = None,
        element_types: Optional[List[str]] = None,
    ) -> int:
        """创建文档切片记录"""
        element_ids_json = json.dumps(element_ids)
        page_numbers_json = json.dumps(page_numbers)
        content_types_json = json.dumps(content_types or [])
        element_types_json = json.dumps(element_types or [])

        # 优先写入类型字段；若表尚未迁移则回退旧 SQL
        sql_full = """
        INSERT INTO document_chunks
        (file_id, chunk_index, chunk_text, char_count, element_count,
         element_ids, page_numbers, content_types, element_types, is_embedded)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        sql_legacy = """
        INSERT INTO document_chunks
        (file_id, chunk_index, chunk_text, char_count, element_count,
         element_ids, page_numbers, is_embedded)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        try:
            return execute_query(
                sql_full,
                (
                    file_id, chunk_index, chunk_text, char_count, element_count,
                    element_ids_json, page_numbers_json,
                    content_types_json, element_types_json, 0,
                ),
            )
        except Exception as e:
            err = str(e).lower()
            if 'content_types' in err or 'element_types' in err or 'unknown column' in err:
                return execute_query(
                    sql_legacy,
                    (
                        file_id, chunk_index, chunk_text, char_count, element_count,
                        element_ids_json, page_numbers_json, 0,
                    ),
                )
            raise

    @staticmethod
    def get_chunks_by_file(file_id: int) -> List[Dict]:
        """获取文件的所有切片"""
        sql = """
        SELECT id, file_id, chunk_index, chunk_text, char_count, element_count,
               element_ids, page_numbers, vector_id, is_embedded, created_at, embedded_at,
               content_types, element_types
        FROM document_chunks
        WHERE file_id = %s
        ORDER BY chunk_index
        """
        sql_legacy = """
        SELECT id, file_id, chunk_index, chunk_text, char_count, element_count,
               element_ids, page_numbers, vector_id, is_embedded, created_at, embedded_at
        FROM document_chunks
        WHERE file_id = %s
        ORDER BY chunk_index
        """

        try:
            rows = fetch_all(sql, (file_id,))
            has_types = True
        except Exception as e:
            err = str(e).lower()
            if 'unknown column' in err or 'content_types' in err or 'element_types' in err:
                rows = fetch_all(sql_legacy, (file_id,))
                has_types = False
            else:
                raise

        chunks = []
        for row in rows:
            element_ids = json.loads(row[6]) if row[6] else []
            page_numbers = json.loads(row[7]) if row[7] else []
            content_types = []
            element_types = []
            if has_types:
                content_types = json.loads(row[12]) if row[12] else []
                element_types = json.loads(row[13]) if row[13] else []

            chunks.append({
                'id': row[0],
                'file_id': row[1],
                'chunk_index': row[2],
                'chunk_text': row[3],
                'char_count': row[4],
                'element_count': row[5],
                'element_ids': element_ids,
                'page_numbers': page_numbers,
                'vector_id': row[8],
                'is_embedded': bool(row[9]),
                'created_at': row[10].isoformat() if row[10] else None,
                'embedded_at': row[11].isoformat() if row[11] else None,
                'content_types': content_types,
                'element_types': element_types,
            })

        return chunks
    
    @staticmethod
    def get_chunk_by_index(file_id: int, chunk_index: int) -> Optional[Dict]:
        """获取指定索引的切片"""
        sql = """
        SELECT id, file_id, chunk_index, chunk_text, char_count, element_count,
               element_ids, page_numbers, vector_id, is_embedded, created_at
        FROM document_chunks
        WHERE file_id = %s AND chunk_index = %s
        """
        
        row = fetch_one(sql, (file_id, chunk_index))
        
        if row:
            # MySQL: JSON字段需要解析
            element_ids = json.loads(row[6]) if row[6] else []
            page_numbers = json.loads(row[7]) if row[7] else []
            
            return {
                'id': row[0],
                'file_id': row[1],
                'chunk_index': row[2],
                'chunk_text': row[3],
                'char_count': row[4],
                'element_count': row[5],
                'element_ids': element_ids,
                'page_numbers': page_numbers,
                'vector_id': row[8],
                'is_embedded': bool(row[9]),
                'created_at': row[10].isoformat() if row[10] else None
            }
        
        return None
    
    @staticmethod
    def update_chunk_embedding_status(
        file_id: int,
        chunk_index: int,
        vector_id: str,
        is_embedded: bool = True
    ):
        """更新切片的向量化状态"""
        sql = """
        UPDATE document_chunks
        SET vector_id = %s, is_embedded = %s, embedded_at = %s
        WHERE file_id = %s AND chunk_index = %s
        """
        
        # MySQL: bool转TINYINT
        is_embedded_int = 1 if is_embedded else 0
        
        execute_query(
            sql,
            (vector_id, is_embedded_int, datetime.now(), file_id, chunk_index)
        )
    
    @staticmethod
    def count_by_file(file_id: int) -> int:
        """统计文件的切片数量"""
        sql = "SELECT COUNT(*) FROM document_chunks WHERE file_id = %s"
        row = fetch_one(sql, (file_id,))
        return row[0] if row else 0
    
    @staticmethod
    def count_embedded_by_file(file_id: int) -> int:
        """统计文件已向量化的切片数量"""
        sql = "SELECT COUNT(*) FROM document_chunks WHERE file_id = %s AND is_embedded = 1"
        row = fetch_one(sql, (file_id,))
        return row[0] if row else 0
    
    @staticmethod
    def search_chunks_by_user(
        user_id: int,
        file_ids: Optional[List[int]] = None,
        limit: int = 500,
    ) -> List[Dict]:
        """
        按用户拉取已嵌入切片（供关键词/语义词面检索打分）。
        """
        conditions = ["fm.user_id = %s", "dc.is_embedded = 1"]
        params: List[Any] = [user_id]

        if file_ids:
            placeholders = ','.join(['%s'] * len(file_ids))
            conditions.append(f"dc.file_id IN ({placeholders})")
            params.extend(file_ids)

        sql = f"""
        SELECT dc.id, dc.file_id, dc.chunk_index, dc.chunk_text, dc.char_count,
               dc.element_count, dc.page_numbers, dc.is_embedded
        FROM document_chunks dc
        INNER JOIN file_metadata fm ON dc.file_id = fm.id
        WHERE {' AND '.join(conditions)}
        ORDER BY dc.file_id, dc.chunk_index
        LIMIT %s
        """
        params.append(limit)

        rows = fetch_all(sql, tuple(params))
        chunks = []
        for row in rows:
            page_numbers = json.loads(row[6]) if row[6] else []
            chunks.append({
                'id': row[0],
                'file_id': row[1],
                'chunk_index': row[2],
                'chunk_text': row[3],
                'char_count': row[4],
                'element_count': row[5],
                'page_numbers': page_numbers,
                'is_embedded': bool(row[7]),
            })
        return chunks

    @staticmethod
    def search_chunks(
        file_id: int,
        search_text: Optional[str] = None,
        element_type: Optional[str] = None
    ) -> List[Dict]:
        """
        搜索切片
        
        Args:
            file_id: 文件ID
            search_text: 搜索文本 (模糊匹配)
            element_type: 元素类型过滤
        """
        conditions = ["file_id = %s"]
        params = [file_id]
        
        if search_text:
            conditions.append("chunk_text LIKE %s")
            params.append(f"%{search_text}%")
        
        # 注意: element_type过滤需要关联document_elements表
        # 这里简化处理，只按文本搜索
        
        sql = f"""
        SELECT id, chunk_index, chunk_text, char_count, element_count,
               page_numbers, is_embedded
        FROM document_chunks
        WHERE {' AND '.join(conditions)}
        ORDER BY chunk_index
        LIMIT 100
        """
        
        rows = fetch_all(sql, tuple(params))
        
        chunks = []
        for row in rows:
            # MySQL: JSON字段需要解析
            page_numbers = json.loads(row[5]) if row[5] else []
            
            chunks.append({
                'id': row[0],
                'chunk_index': row[1],
                'chunk_text': row[2][:200] + '...' if len(row[2]) > 200 else row[2],  # 预览
                'char_count': row[3],
                'element_count': row[4],
                'page_numbers': page_numbers,
                'is_embedded': bool(row[6])
            })
        
        return chunks
