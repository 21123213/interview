"""RAG功能模块 - 文档处理和检索"""
import os
import tempfile
import time
from typing import List, Dict, Any, Optional, Iterator, Tuple
from pathlib import Path
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

from app.core.llm_utils import (
    make_dashscope_chat,
    normalize_llm_text,
    extract_stream_delta,
)
from app.core import rag_trace


class RAGService:
    """RAG服务 - 文档向量化和检索"""
    
    def __init__(self):
        # 直接从环境变量读取
        self.api_key = os.getenv('DASHSCOPE_EMBEDDING_API_KEY')
        self.embedding_model = os.getenv('DASHSCOPE_EMBEDDING_MODEL', 'text-embedding-v4')
        self.persist_directory = os.getenv('CHROMA_PERSIST_DIR', 'db/chroma_db')
        
        # 初始化embeddings
        self.embeddings = DashScopeEmbeddings(
            model=self.embedding_model,
            dashscope_api_key=self.api_key
        )
        
        # 初始化向量数据库
        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
            collection_metadata={"hnsw:space": "cosine"}
        )
    
    def process_file(self, file_path: str, file_type: str) -> int:
        """
        处理文件：加载、切分、向量化
        :param file_path: 文件路径
        :param file_type: 文件类型（.txt, .pdf等）
        :return: 切片数量
        """
        # 加载文档
        if file_type.lower() == '.txt':
            loader = TextLoader(file_path, encoding='utf-8')
        elif file_type.lower() == '.pdf':
            loader = PyPDFLoader(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")
        
        documents = loader.load()
        
        # 切分文档
        chunks = self.split_documents(documents)
        
        # 向量化并存储
        if chunks:
            self.vector_store.add_documents(chunks)
        
        return len(chunks)
    
    def process_file_content(self, content: bytes, filename: str, file_type: str) -> int:
        """
        处理文件内容（二进制）
        :param content: 文件二进制内容
        :param filename: 文件名
        :param file_type: 文件类型
        :return: 切片数量
        """
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_type) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            chunks_count = self.process_file(tmp_path, file_type)
            return chunks_count
        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    def split_documents(self, documents, chunk_size: int = 800, chunk_overlap: int = 100):
        """切分文档"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)
        
        # 过滤空chunk
        chunks = [c for c in chunks if c.page_content and c.page_content.strip()]
        
        return chunks
    
    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        检索相关文档
        :param query: 查询文本
        :param top_k: 返回前k个结果
        :return: 相关文档列表
        """
        retriever = self.vector_store.as_retriever(
            search_kwargs={"k": top_k}
        )
        
        relevant_docs = retriever.invoke(query)
        
        # 格式化结果
        results = []
        for doc in relevant_docs:
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": 0.0  # Chroma默认不返回分数，可以通过similarity_search_with_score获取
            })
        
        return results
    
    def retrieve_with_scores(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        检索相关文档并返回相似度分数
        :param query: 查询文本
        :param top_k: 返回前k个结果
        :return: 相关文档列表（带分数）
        """
        results = self.vector_store.similarity_search_with_score(query, k=top_k)
        
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score)
            })
        
        return formatted_results
    
    def _build_answer_messages(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[BaseMessage], str]:
        """构建答案生成 prompt；无检索结果时返回 (空, 固定提示)。"""
        if not context_docs:
            return [], "抱歉，我没有在您的文档中找到相关信息。请确认已上传并处理完成相关文件。"

        context_parts: List[str] = []
        for i, doc in enumerate(context_docs, start=1):
            content = doc.get('content') or doc.get('chunk_text') or ''
            meta = doc.get('metadata') or {}
            pages = meta.get('page_numbers') or []
            page_hint = f" (页码: {pages})" if pages else ''
            context_parts.append(f"--- 文档片段 {i}{page_hint} ---\n{content[:4000]}")

        context_block = '\n\n'.join(context_parts)

        history_lines: List[str] = []
        if history:
            # 记忆侧已限制轮数与总 token，此处使用完整内容便于指代理解
            for msg in history:
                role = msg.get('role', 'user')
                text = msg.get('content') or ''
                history_lines.append(f"{role}: {text}")
        history_block = '\n'.join(history_lines) if history_lines else '（无）'

        system = SystemMessage(content=(
            "你是基于用户上传文档的 RAG 问答助手。只能依据提供的文档片段回答；"
            "若片段不足以回答，请明确说明。回答使用中文，简洁准确。"
        ))
        human = HumanMessage(content=f"""对话历史（供理解指代，勿当作事实来源）:
{history_block}

用户问题:
{query}

参考文档片段:
{context_block}

请给出完整回答。若文档中没有相关信息，请说明无法从已上传文档中回答。""")
        return [system, human], ''

    def _answer_chat_model(self, streaming: bool = True):
        model = (
            os.getenv('DASHSCOPE_ANSWER_MODEL')
            or os.getenv('DASHSCOPE_STRONG_MODEL')
            or 'qwen-plus'
        ).strip()
        return make_dashscope_chat(
            model=model,
            api_key=os.getenv('DASHSCOPE_API_KEY') or self.api_key,
            temperature=0.3,
            streaming=streaming,
        )

    def _trace_generate_meta(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        messages: List[BaseMessage],
        *,
        streaming: bool,
        fallback: bool = False,
    ) -> Dict[str, Any]:
        prompt_chars = sum(len(getattr(m, 'content', '') or '') for m in messages)
        meta: Dict[str, Any] = {
            'query': rag_trace.truncate_text(query),
            'context_chunks': rag_trace.summarize_chunks(context_docs),
            'context_count': len(context_docs or []),
            'prompt_chars': prompt_chars,
            'streaming': streaming,
            'fallback': fallback,
        }
        if rag_trace.full_mode() and messages:
            meta['prompt_preview'] = rag_trace.truncate_text(
                '\n'.join(str(getattr(m, 'content', '') or '') for m in messages),
                max_len=4000,
            )
        else:
            meta['prompt_preview'] = rag_trace.truncate_text(
                messages[-1].content if messages else '',
                max_len=200,
            )
        return meta

    def generate_answer(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """基于检索切片与可选对话历史生成答案。"""
        t0 = time.perf_counter()
        messages, fallback = self._build_answer_messages(query, context_docs, history)
        if fallback:
            rag_trace.emit(
                'generate_answer',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    **self._trace_generate_meta(
                        query, context_docs, messages, streaming=False, fallback=True
                    ),
                    'answer_len': len(fallback),
                    'answer_preview': rag_trace.truncate_text(fallback),
                },
            )
            return fallback

        chat = self._answer_chat_model(streaming=False)
        try:
            resp = chat.invoke(messages)
            answer = normalize_llm_text(resp.content) or "抱歉，未能生成有效回答。"
            rag_trace.emit(
                'generate_answer',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    **self._trace_generate_meta(
                        query, context_docs, messages, streaming=False
                    ),
                    'answer_len': len(answer),
                    'answer_preview': rag_trace.truncate_text(answer),
                },
            )
            return answer
        except Exception as e:
            print(f"❌ generate_answer 失败: {e}")
            err_msg = "抱歉，生成回答时出现错误，请稍后重试。"
            rag_trace.emit(
                'generate_answer',
                status='error',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    **self._trace_generate_meta(
                        query, context_docs, messages, streaming=False
                    ),
                    'answer_len': len(err_msg),
                },
                message=str(e),
                error_type=type(e).__name__,
            )
            return err_msg

    def generate_answer_stream(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[str]:
        """流式生成答案，逐块 yield 文本增量。"""
        t0 = time.perf_counter()
        messages, fallback = self._build_answer_messages(query, context_docs, history)
        if fallback:
            rag_trace.emit(
                'generate_answer',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    **self._trace_generate_meta(
                        query, context_docs, messages, streaming=True, fallback=True
                    ),
                    'answer_len': len(fallback),
                    'answer_preview': rag_trace.truncate_text(fallback),
                },
            )
            yield fallback
            return

        chat = self._answer_chat_model(streaming=True)
        parts: List[str] = []
        try:
            for chunk in chat.stream(messages):
                delta = extract_stream_delta(chunk)
                if delta:
                    parts.append(delta)
                    yield delta
            answer = ''.join(parts)
            rag_trace.emit(
                'generate_answer',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    **self._trace_generate_meta(
                        query, context_docs, messages, streaming=True
                    ),
                    'answer_len': len(answer),
                    'answer_preview': rag_trace.truncate_text(answer),
                },
            )
        except Exception as e:
            print(f"❌ generate_answer_stream 失败: {e}")
            err_msg = "抱歉，生成回答时出现错误，请稍后重试。"
            rag_trace.emit(
                'generate_answer',
                status='error',
                latency_ms=(time.perf_counter() - t0) * 1000,
                data={
                    **self._trace_generate_meta(
                        query, context_docs, messages, streaming=True
                    ),
                    'answer_len': len(err_msg),
                    'partial_len': sum(len(p) for p in parts),
                },
                message=str(e),
                error_type=type(e).__name__,
            )
            yield err_msg


# 全局RAG服务实例
rag_service = RAGService()


def process_document(file_path: str, file_type: str) -> int:
    """处理文档的便捷函数"""
    return rag_service.process_file(file_path, file_type)


def search_documents(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """搜索文档的便捷函数"""
    return rag_service.retrieve_with_scores(query, top_k)


# ==================== 新增: Milvus向量化支持 ====================

def embed_text(text: str) -> List[float]:
    """
    将文本转换为向量
    用于Milvus向量存储
    
    Args:
        text: 输入文本
    
    Returns:
        向量列表 (text-embedding-v4 默认 1024 维)
    """
    try:
        embedding = rag_service.embeddings.embed_query(text)
        return embedding
    except Exception as e:
        print(f"❌ 文本向量化失败: {e}")
        raise


def embed_document(text: str) -> List[float]:
    """
    将文档片段转换为向量（text_type=document，用于入库索引）
    """
    try:
        embeddings = rag_service.embeddings.embed_documents([text])
        return embeddings[0]
    except Exception as e:
        print(f"❌ 文档向量化失败: {e}")
        raise


def embed_texts_batch(texts: List[str]) -> List[List[float]]:
    """
    批量将文本转换为向量
    
    Args:
        texts: 文本列表
    
    Returns:
        向量列表
    """
    try:
        embeddings = rag_service.embeddings.embed_documents(texts)
        return embeddings
    except Exception as e:
        print(f"❌ 批量向量化失败: {e}")
        raise

