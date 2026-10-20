"""
Milvus 向量数据库服务
支持单Collection多用户隔离的向量存储和检索
通过MILVUS_ENABLED环境变量控制是否启用
"""
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# 延迟导入pymilvus，避免启动时导入失败导致系统崩溃
_pymilvus = None

def _get_pymilvus():
    """延迟导入pymilvus"""
    global _pymilvus
    if _pymilvus is None:
        try:
            from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
            _pymilvus = {
                'connections': connections,
                'Collection': Collection,
                'CollectionSchema': CollectionSchema,
                'FieldSchema': FieldSchema,
                'DataType': DataType,
                'utility': utility
            }
        except ImportError as e:
            print(f"⚠️  pymilvus导入失败: {e}")
            return None
    return _pymilvus


class MilvusService:
    """Milvus 向量数据库服务类"""
    
    def __init__(self):
        # 检查是否启用Milvus
        self.enabled = os.getenv('MILVUS_ENABLED', 'false').lower() == 'true'
        
        if not self.enabled:
            print("⚠️  Milvus已禁用 (MILVUS_ENABLED=false)")
            print("   系统将跳过向量存储，其他功能正常")
            return
        
        # 部署模式：lite 或 standalone
        self.mode = os.getenv('MILVUS_MODE', 'lite').lower()
        
        # Milvus Lite 配置
        self.lite_path = os.getenv('MILVUS_LITE_PATH', './db/milvus_lite.db')
        
        # Milvus Standalone 配置
        self.host = os.getenv('MILVUS_HOST', 'localhost')
        self.port = int(os.getenv('MILVUS_PORT', '19530'))
        self.user = os.getenv('MILVUS_USER', '')
        self.password = os.getenv('MILVUS_PASSWORD', '')
        
        self.collection_name = os.getenv('MILVUS_COLLECTION_NAME', 'document_vectors')
        # text-embedding-v3 默认输出 1024 维
        dim_str = os.getenv('MILVUS_EMBEDDING_DIM', '1024').split('#')[0].strip()
        self.dim = int(dim_str)
        self.collection = None
        self._connected = False
        # Collection.load() 只需成功一次；每题都 load 会触发 gRPC too_many_pings
        self._collection_loaded = False
        
        print(f"📋 Milvus模式: {self.mode.upper()}")
        if self.mode == 'lite':
            print(f"   数据库路径: {self.lite_path}")
        else:
            print(f"   服务地址: {self.host}:{self.port}")
        
        # 不在初始化时连接，延迟到第一次使用
    
    def connect(self):
        """连接到Milvus"""
        if not self.enabled:
            return False
            
        if self._connected:
            return True
        
        # 延迟导入pymilvus
        pm = _get_pymilvus()
        if pm is None:
            print("❌ pymilvus未安装，请运行: pip install pymilvus")
            self.enabled = False
            return False
            
        try:
            if self.mode == 'lite':
                lite_dir = os.path.dirname(os.path.abspath(self.lite_path))
                if lite_dir:
                    os.makedirs(lite_dir, exist_ok=True)

                pm['connections'].connect(
                    alias="default",
                    uri=self.lite_path
                )
                print(f"✅ Milvus Lite连接成功: {self.lite_path}")
            else:
                # Milvus Standalone/Cluster 模式
                conn_params = {
                    "alias": "default",
                    "host": self.host,
                    "port": self.port
                }
                
                if self.user:
                    conn_params["user"] = self.user
                    conn_params["password"] = self.password
                
                pm['connections'].connect(**conn_params)
                print(f"✅ Milvus Standalone连接成功: {self.host}:{self.port}")
            
            self._connected = True
            self._collection_loaded = False
            # 确保Collection存在
            self.ensure_collection()
            return True
            
        except Exception as e:
            print(f"❌ Milvus连接失败: {e}")
            print("   系统将继续运行，但向量存储功能不可用")
            if self.mode == 'lite':
                print("   💡 提示：请安装 milvus-lite: pip install milvus-lite")
            else:
                print("   💡 提示：确保Milvus服务已启动")
            self.enabled = False
            return False

    def _ensure_collection_loaded(self) -> bool:
        """首次检索/查询前 load 一次；之后复用，避免 keepalive 过密。"""
        if not self.collection:
            return False
        if self._collection_loaded:
            return True
        try:
            self.collection.load()
            self._collection_loaded = True
            return True
        except Exception as e:
            print(f"❌ Collection.load 失败: {e}")
            self._collection_loaded = False
            return False
    
    def create_collection_schema(self):
        """创建Collection Schema"""
        pm = _get_pymilvus()
        if pm is None:
            return None
            
        fields = [
            pm['FieldSchema'](
                name="id", 
                dtype=pm['DataType'].VARCHAR, 
                max_length=100, 
                is_primary=True,
                description="向量ID格式: user_{user_id}_file_{file_id}_chunk_{chunk_idx}"
            ),
            pm['FieldSchema'](
                name="user_id", 
                dtype=pm['DataType'].INT64,
                description="用户ID - 用于多用户隔离"
            ),
            pm['FieldSchema'](
                name="file_id", 
                dtype=pm['DataType'].INT64,
                description="文件ID"
            ),
            pm['FieldSchema'](
                name="chunk_index", 
                dtype=pm['DataType'].INT64,
                description="切片索引"
            ),
            pm['FieldSchema'](
                name="embedding", 
                dtype=pm['DataType'].FLOAT_VECTOR, 
                dim=self.dim,
                description="文本向量"
            ),
            pm['FieldSchema'](
                name="chunk_text", 
                dtype=pm['DataType'].VARCHAR, 
                max_length=65535,
                description="切片文本内容"
            ),
            pm['FieldSchema'](
                name="metadata", 
                dtype=pm['DataType'].JSON,
                description="元数据(文件名、页码等)"
            )
        ]
        
        schema = pm['CollectionSchema'](
            fields=fields,
            description="RAG系统向量存储",
            enable_dynamic_field=False
        )
        
        return schema

    def _get_collection_dim(self) -> Optional[int]:
        """读取已有 Collection 的向量维度"""
        if not self.collection:
            return None
        for field in self.collection.schema.fields:
            if field.name == 'embedding':
                return field.params.get('dim') if hasattr(field, 'params') else getattr(field, 'dim', None)
        return None

    def ensure_collection(self):
        """确保Collection存在并创建HNSW索引"""
        if not self.enabled:
            return False

        if not self._connected:
            if not self.connect():
                return False

        pm = _get_pymilvus()
        if pm is None:
            return False

        if pm['utility'].has_collection(self.collection_name):
            self.collection = pm['Collection'](self.collection_name)
            existing_dim = self._get_collection_dim()
            if existing_dim and existing_dim != self.dim:
                print(
                    f"⚠️  Collection维度不匹配: 已有={existing_dim}, "
                    f"当前配置={self.dim}，正在重建..."
                )
                pm['utility'].drop_collection(self.collection_name)
                self.collection = None
                self._collection_loaded = False
            else:
                print(f"✅ Collection已存在: {self.collection_name} (dim={existing_dim})")
                return True

        print(f"📦 创建Collection: {self.collection_name} (dim={self.dim})")
        self._collection_loaded = False

        schema = self.create_collection_schema()
        if schema is None:
            return False

        self.collection = pm['Collection'](
            name=self.collection_name,
            schema=schema
        )

        index_params = {
            "index_type": "HNSW",
            "metric_type": "IP",
            "params": {
                "M": 16,
                "efConstruction": 200
            }
        }

        self.collection.create_index(
            field_name="embedding",
            index_params=index_params
        )

        print(f"✅ Collection创建成功 (dim={self.dim})")
        return True

    def insert_vectors(
        self, 
        user_id: int, 
        file_id: int, 
        chunks: List[Dict[str, Any]]
    ) -> int:
        """插入向量数据"""
        if not self.enabled:
            print("⚠️  Milvus未启用，跳过向量插入")
            return 0
            
        # 确保已连接
        if not self._connected:
            if not self.connect():
                return 0
            
        if not chunks:
            return 0

        try:
            data = []
            for chunk in chunks:
                embedding = chunk['embedding']
                if len(embedding) != self.dim:
                    raise ValueError(
                        f"chunk_index={chunk['chunk_index']} 向量维度 {len(embedding)} "
                        f"与 Collection 配置 {self.dim} 不一致"
                    )

                chunk_idx = chunk['chunk_index']
                data.append({
                    "id": f"user_{user_id}_file_{file_id}_chunk_{chunk_idx}",
                    "user_id": user_id,
                    "file_id": file_id,
                    "chunk_index": chunk_idx,
                    "embedding": embedding,
                    "chunk_text": chunk['text'][:65535],
                    "metadata": chunk.get('metadata', {})
                })

            print(f"📤 正在写入 Milvus: {len(data)} 条向量 (dim={self.dim})...")
            self.collection.insert(data)
            self.collection.flush()

            print(f"✅ 已插入 {len(data)} 个向量 (user={user_id}, file={file_id})")
            return len(data)
        except Exception as e:
            print(f"❌ 向量插入失败: {e}")
            raise
    
    def search(
        self, 
        user_id: int, 
        query_embedding: List[float], 
        top_k: int = 5,
        file_ids: Optional[List[int]] = None,
        _reloaded: bool = False,
    ) -> List[Dict[str, Any]]:
        """向量检索"""
        if not self.enabled:
            print("⚠️  Milvus未启用，无法检索")
            return []
            
        # 确保已连接
        if not self._connected:
            if not self.connect():
                return []
        
        try:
            if not self._ensure_collection_loaded():
                return []
            
            # 构建过滤表达式
            expr = f"user_id == {user_id}"
            if file_ids:
                file_ids_str = ",".join(map(str, file_ids))
                expr += f" and file_id in [{file_ids_str}]"
            
            # HNSW搜索参数
            search_params = {
                "metric_type": "IP",
                "params": {"ef": 64}
            }
            
            # 执行搜索
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["chunk_text", "file_id", "chunk_index", "metadata"]
            )
            
            # 格式化结果
            formatted_results = []
            for hits in results:
                for hit in hits:
                    formatted_results.append({
                        "id": hit.id,
                        "distance": hit.distance,
                        "score": hit.distance,
                        "chunk_text": hit.entity.get("chunk_text"),
                        "file_id": hit.entity.get("file_id"),
                        "chunk_index": hit.entity.get("chunk_index"),
                        "metadata": hit.entity.get("metadata", {})
                    })
            
            return formatted_results
        except Exception as e:
            # GOAWAY / 未加载：最多再 load 一次后重试，避免死循环
            err = str(e).lower()
            if (not _reloaded) and (
                'not loaded' in err or 'goaway' in err or 'unavailable' in err
            ):
                self._collection_loaded = False
                print(f"⚠️  向量检索异常，尝试重新 load 一次: {e}")
                return self.search(
                    user_id, query_embedding, top_k, file_ids, _reloaded=True
                )
            print(f"❌ 向量检索失败: {e}")
            return []
    
    def delete_by_file(self, user_id: int, file_id: int) -> int:
        """删除指定文件的所有向量"""
        if not self.enabled:
            return 0
            
        if not self._connected:
            if not self.connect():
                return 0
        
        try:
            expr = f"user_id == {user_id} and file_id == {file_id}"
            
            if not self._ensure_collection_loaded():
                return 0
            count_result = self.collection.query(
                expr=expr,
                output_fields=["id"]
            )
            count = len(count_result)
            
            self.collection.delete(expr)
            self.collection.flush()
            
            print(f"✅ 已删除 {count} 个向量 (user={user_id}, file={file_id})")
            return count
        except Exception as e:
            print(f"❌ 向量删除失败: {e}")
            return 0
    
    def delete_by_user(self, user_id: int) -> int:
        """删除用户的所有向量"""
        if not self.enabled:
            return 0
            
        if not self._connected:
            if not self.connect():
                return 0
        
        try:
            expr = f"user_id == {user_id}"
            
            if not self._ensure_collection_loaded():
                return 0
            count_result = self.collection.query(
                expr=expr,
                output_fields=["id"]
            )
            count = len(count_result)
            
            self.collection.delete(expr)
            self.collection.flush()
            
            print(f"✅ 已删除用户 {user_id} 的全部 {count} 个向量")
            return count
        except Exception as e:
            print(f"❌ 向量删除失败: {e}")
            return 0
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取Collection统计信息"""
        if not self.enabled:
            return {"enabled": False}
            
        if not self._connected:
            if not self.connect():
                return {"enabled": False}
        
        try:
            pm = _get_pymilvus()
            if not self._ensure_collection_loaded():
                return {"enabled": False, "error": "collection load failed"}
            
            stats = {
                "enabled": True,
                "collection_name": self.collection_name,
                "total_entities": self.collection.num_entities,
                "is_loaded": pm['utility'].load_state(self.collection_name),
                "index_info": self.collection.indexes
            }
            
            return stats
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
            return {"enabled": False, "error": str(e)}
    
    def disconnect(self):
        """断开连接"""
        if self._connected:
            pm = _get_pymilvus()
            if pm:
                pm['connections'].disconnect("default")
            self._connected = False
            self._collection_loaded = False
            print("🔌 Milvus连接已断开")


# 全局单例
milvus_service = MilvusService()


# 测试函数
def test_milvus():
    """测试Milvus服务"""
    print("\n" + "=" * 50)
    print("测试Milvus服务")
    print("=" * 50)
    
    if not milvus_service.enabled:
        print("⚠️  Milvus未启用，跳过测试")
        return
    
    # 测试连接
    if not milvus_service.connect():
        print("❌ 无法连接Milvus，测试终止")
        return
    
    # 1. 测试插入
    test_chunks = [
        {
            "chunk_index": 0,
            "embedding": [0.1] * 1536,
            "text": "这是测试文本1",
            "metadata": {"page": 1, "filename": "test.pdf"}
        },
        {
            "chunk_index": 1,
            "embedding": [0.2] * 1536,
            "text": "这是测试文本2",
            "metadata": {"page": 2, "filename": "test.pdf"}
        }
    ]
    
    count = milvus_service.insert_vectors(
        user_id=999,
        file_id=888,
        chunks=test_chunks
    )
    print(f"✅ 插入测试: {count} 个向量")
    
    # 2. 测试搜索
    query_embedding = [0.15] * 1536
    results = milvus_service.search(
        user_id=999,
        query_embedding=query_embedding,
        top_k=2
    )
    print(f"✅ 搜索测试: 找到 {len(results)} 个结果")
    for r in results:
        print(f"   - Score: {r['score']:.4f}, Text: {r['chunk_text']}")
    
    # 3. 测试删除
    deleted = milvus_service.delete_by_file(user_id=999, file_id=888)
    print(f"✅ 删除测试: 删除 {deleted} 个向量")
    
    # 4. 获取统计
    stats = milvus_service.get_collection_stats()
    print(f"✅ Collection统计: {stats.get('total_entities', 0)} 个向量")
    
    print("\n✅ 所有测试通过!")


if __name__ == "__main__":
    test_milvus()
