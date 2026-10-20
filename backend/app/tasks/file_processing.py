"""
文件处理后台任务
包含文档解析、切片、LLM 增强、向量化等步骤
"""
import os
from typing import Any, Dict, List, Optional, Tuple

from app.core.redis_manager import redis_manager
from app.core.milvus_service import milvus_service
from app.models.file import FileMetadataModel
from app.models.document import DocumentElementModel, DocumentChunkModel


# ==================== 配置 ====================

def _ocr_languages() -> List[str]:
    raw = os.getenv('UNSTRUCTURED_OCR_LANGUAGES', 'chi_sim,eng')
    return [lang.strip() for lang in raw.split(',') if lang.strip()]


def _chunk_by_title_config() -> Dict[str, int]:
    max_chars = int(os.getenv('CHUNK_MAX_CHARACTERS', '2500'))
    new_after = int(os.getenv('CHUNK_NEW_AFTER_N_CHARS', '2000'))
    combine_under = int(os.getenv('CHUNK_COMBINE_TEXT_UNDER_N_CHARS', '500'))
    overlap = int(os.getenv('CHUNK_OVERLAP', '300'))
    if overlap >= max_chars:
        overlap = max(0, max_chars // 4)
    if new_after > max_chars:
        new_after = max_chars
    if combine_under > max_chars:
        combine_under = max_chars
    return {
        'max_characters': max_chars,
        'new_after_n_chars': new_after,
        'combine_text_under_n_chars': combine_under,
        'overlap': overlap,
    }


def _llm_enhance_mode() -> str:
    """off | mixed | all"""
    return os.getenv('LLM_ENHANCE_MODE', 'mixed').strip().lower()


def _pdf_strategy() -> str:
    return os.getenv('UNSTRUCTURED_PDF_STRATEGY', 'hi_res').strip().lower()


# ==================== 进度与错误 ====================

def _update_embedding_progress(file_id: int, current: int, total: int):
    progress = 65 + int((current / total) * 30) if total else 65
    redis_manager.set_task_progress(
        file_id=file_id,
        status='processing',
        progress=progress,
        current_step='embedding',
        message=f'向量化中... {current}/{total}',
        processed_chunks=current,
    )
    from app.api.websocket import broadcast_progress_sync
    broadcast_progress_sync(file_id, {
        'status': 'processing',
        'progress': progress,
        'current_step': 'embedding',
        'message': f'向量化中... {current}/{total}',
        'data': {'current': current, 'total': total},
    })


def _update_summarization_progress(file_id: int, current: int, total: int):
    progress = 55 + int((current / total) * 10) if total else 55
    redis_manager.set_task_progress(
        file_id=file_id,
        status='processing',
        progress=progress,
        current_step='summarization',
        message=f'内容增强中... {current}/{total}',
        processed_chunks=current,
    )
    from app.api.websocket import broadcast_progress_sync
    broadcast_progress_sync(file_id, {
        'status': 'processing',
        'progress': progress,
        'current_step': 'summarization',
        'message': f'内容增强中... {current}/{total}',
        'data': {'current': current, 'total': total},
    })


def _reset_stage_progress(
    file_id: int,
    *,
    progress: int,
    current_step: str,
    message: str,
):
    """切换阶段时清零 processed_chunks，避免 UI 闪现上一阶段的 x/x 完成态"""
    redis_manager.set_task_progress(
        file_id=file_id,
        status='processing',
        progress=progress,
        current_step=current_step,
        message=message,
        processed_chunks=0,
    )
    from app.api.websocket import broadcast_progress_sync
    broadcast_progress_sync(file_id, {
        'status': 'processing',
        'progress': progress,
        'current_step': current_step,
        'message': message,
        'data': {'current': 0, 'total': 0},
    })


def _handle_processing_failure(file_id: int, exc: Exception):
    FileMetadataModel.update_file_status(file_id, 'failed', error_message=str(exc))
    redis_manager.set_task_progress(
        file_id=file_id,
        status='failed',
        progress=0,
        current_step='error',
        message=f'处理失败: {str(exc)}',
    )
    redis_manager.release_file_lock(file_id)
    print(f"❌ 任务失败 [file_id={file_id}]: {exc}")


# ==================== 主流程 ====================

def process_file_background(file_id: int, file_path: str, user_id: int):
    try:
        print(f"\n{'='*60}")
        print(f"开始处理文件: {file_id} (用户: {user_id})")
        print(f"{'='*60}\n")

        from app.api.websocket import broadcast_progress_sync

        # ===== 1. Partitioning =====
        print("📄 [1/4] 解析文档...")
        _reset_stage_progress(
            file_id,
            progress=10,
            current_step='parsing',
            message='正在解析文档...',
        )

        raw_elements, element_dicts = parse_document_with_unstructured(file_path)
        elements_count = save_elements_to_db(file_id, element_dicts)
        elements_stats = count_element_types(element_dicts)
        FileMetadataModel.update_field(file_id, 'total_elements', elements_count)
        FileMetadataModel.update_field(file_id, 'elements_stats', elements_stats)

        print(f"✅ 解析完成: {elements_count} 个元素")
        print(f"   元素统计: {elements_stats}")

        # 解析完成立刻广播，前端可回填 Partitioning
        redis_manager.set_task_progress(
            file_id=file_id, status='processing', progress=35,
            current_step='parsing', message=f'解析完成，共{elements_count}个元素',
            processed_chunks=0,
        )
        broadcast_progress_sync(file_id, {
            'status': 'processing', 'progress': 35,
            'current_step': 'parsing',
            'message': f'解析完成，共{elements_count}个元素',
            'data': {'elements_count': elements_count},
        })

        element_id_map = _build_element_id_map(element_dicts)

        # ===== 2. Chunking（先切完入库，再增强）=====
        print("\n✂️  [2/4] 生成切片...")
        _reset_stage_progress(
            file_id,
            progress=40,
            current_step='chunking',
            message='正在生成切片...',
        )

        chunk_cfg = _chunk_by_title_config()
        unstructured_chunks = chunk_elements_by_title(raw_elements)
        print(
            f"   chunk_by_title: max={chunk_cfg['max_characters']}, "
            f"soft={chunk_cfg['new_after_n_chars']}, overlap={chunk_cfg['overlap']}, "
            f"chunks={len(unstructured_chunks)}"
        )

        meta = FileMetadataModel.get_file_by_id(file_id) or {}
        doc_title = _document_title(
            meta.get('original_filename') or meta.get('filename') or file_path
        )
        print(f"   doc_title for chunks: {doc_title or '(empty)'}")

        chunks = build_basic_chunk_records(
            unstructured_chunks,
            element_id_map=element_id_map,
            doc_title=doc_title,
        )
        chunks_count = save_chunks_to_db(file_id, chunks)
        FileMetadataModel.update_field(file_id, 'total_chunks', chunks_count)
        print(f"✅ 切片入库完成: {chunks_count} 个（增强前原文，可回填 Chunking）")

        redis_manager.set_task_progress(
            file_id=file_id, status='processing', progress=50,
            current_step='chunking',
            message=f'切片生成完成，共{chunks_count}个切片',
            processed_chunks=0,
        )
        broadcast_progress_sync(file_id, {
            'status': 'processing', 'progress': 50,
            'current_step': 'chunking',
            'message': f'切片生成完成，共{chunks_count}个切片',
            'data': {'chunks_count': chunks_count},
        })

        # ===== 3. Summarization / LLM 增强 =====
        enhance_mode = _llm_enhance_mode()
        print(f"\n📝 [3/4] 内容增强 (mode={enhance_mode})...")
        _reset_stage_progress(
            file_id,
            progress=55,
            current_step='summarization',
            message='正在处理切片内容...',
        )

        chunks = enhance_chunk_records(
            chunks,
            progress_callback=lambda c, t: _update_summarization_progress(file_id, c, t),
        )
        print(f"✅ 内容增强完成: {chunks_count} 个 (模式: {enhance_mode})")

        broadcast_progress_sync(file_id, {
            'status': 'processing', 'progress': 65,
            'current_step': 'summarization',
            'message': f'内容增强完成，共{chunks_count}个切片',
            'data': {'current': chunks_count, 'total': chunks_count},
        })

        # ===== 4. Embedding =====
        print("\n🧮 [4/4] 向量化...")
        _reset_stage_progress(
            file_id,
            progress=65,
            current_step='embedding',
            message='正在向量化...',
        )

        embedded_count = vectorize_and_store(
            file_id=file_id,
            user_id=user_id,
            chunks=chunks,
            progress_callback=lambda c, t: _update_embedding_progress(file_id, c, t),
        )
        FileMetadataModel.update_field(file_id, 'embedded_chunks', embedded_count)
        print(f"✅ 向量化完成: {embedded_count} 个向量")

        FileMetadataModel.update_file_status(file_id, 'processed', chunks_count=chunks_count)
        redis_manager.set_task_progress(
            file_id=file_id, status='processed', progress=100,
            current_step='completed', message='处理完成！',
            processed_chunks=chunks_count,
        )
        broadcast_progress_sync(file_id, {
            'status': 'processed', 'progress': 100,
            'current_step': 'completed', 'message': '处理完成！',
            'data': {
                'elements_count': elements_count,
                'chunks_count': chunks_count,
                'embedded_count': embedded_count,
            },
        })

        redis_manager.invalidate_user_files_cache(user_id)
        # 语料变更：抬升 corpus_ver，使旧 rag:qa:* 自然 miss（不碰 session 窗口）
        from app.core.qa_cache import bump_corpus_version
        bump_corpus_version(user_id)
        redis_manager.release_file_lock(file_id)

        print(f"\n{'='*60}")
        print(f"✅ 文件处理完成: {file_id}")
        print(f"   元素: {elements_count} | 切片: {chunks_count} | 向量: {embedded_count}")
        print(f"{'='*60}\n")

        return {
            'status': 'success',
            'file_id': file_id,
            'elements_count': elements_count,
            'chunks_count': chunks_count,
            'embedded_count': embedded_count,
        }

    except Exception as e:
        print(f"❌ 文件处理失败: {e}")
        import traceback
        traceback.print_exc()
        _handle_processing_failure(file_id, e)
        raise


def delete_file_vectors(user_id: int, file_id: int):
    try:
        deleted_count = milvus_service.delete_by_file(user_id, file_id)
        redis_manager.invalidate_user_files_cache(user_id)
        # 删除向量 = 语料变更，失效该用户 QA 答案缓存
        from app.core.qa_cache import bump_corpus_version
        bump_corpus_version(user_id)
        return {'status': 'success', 'deleted_count': deleted_count}
    except Exception as e:
        print(f"❌ 删除向量失败: {e}")
        raise


def save_message_to_db(session_id: str, role: str, content: str, sources: list = None):
    try:
        from app.models.chat import ChatMessageModel
        ChatMessageModel.create_message(
            session_id=session_id, role=role, content=content, sources=sources,
        )
    except Exception as e:
        print(f"⚠️  保存消息到数据库失败: {e}")


# ==================== 文档解析 ====================

def parse_document_with_unstructured(file_path: str) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """
    解析文档，对齐 ai.ipynb 的 hi_res 配置。
    返回 (原始 Element 列表, 用于入库的元素 dict 列表)
    """
    ext = os.path.splitext(file_path)[1].lower()
    languages = _ocr_languages()

    if ext == '.pdf':
        raw_elements = _parse_pdf(file_path, languages)
    elif ext == '.docx':
        from unstructured.partition.docx import partition_docx
        raw_elements = partition_docx(filename=file_path, languages=languages)
    elif ext in ('.txt', '.md'):
        from unstructured.partition.text import partition_text
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            raw_elements = partition_text(text=f.read(), languages=languages)
    else: 
        from unstructured.partition.auto import partition
        raw_elements = partition(
            filename=file_path,
            strategy=_pdf_strategy(),
            include_page_breaks=True,
            infer_table_structure=True,
            languages=languages,
        )

    element_dicts = []
    for idx, elem in enumerate(raw_elements):
        metadata = elem.metadata.to_dict() if hasattr(elem.metadata, 'to_dict') else {}
        element_dicts.append({
            'index': idx,
            'type': elem.category,
            'text': str(elem),
            'metadata': metadata,
        })

    return raw_elements, element_dicts


def _parse_pdf(file_path: str, languages: List[str]) -> List[Any]:
    from unstructured.partition.pdf import partition_pdf

    strategy = _pdf_strategy()
    hi_res_kwargs = {
        'filename': file_path,
        'strategy': 'hi_res',
        'include_page_breaks': True,
        'infer_table_structure': True,
        'extract_image_block_types': ['Image'],
        'extract_image_block_to_payload': True,
        'languages': languages,
    }

    if strategy == 'fast':
        print("   PDF 解析策略: fast")
        return partition_pdf(
            filename=file_path,
            strategy='fast',
            include_page_breaks=True,
            infer_table_structure=False,
            languages=languages,
        )

    try:
        print("   PDF 解析策略: hi_res (含表格结构 + 图片提取)")
        return partition_pdf(**hi_res_kwargs)
    except Exception as e:
        print(f"⚠️  hi_res 解析失败，降级为 fast: {e}")
        return partition_pdf(
            filename=file_path,
            strategy='fast',
            include_page_breaks=True,
            infer_table_structure=False,
            languages=languages,
        )


# ==================== 切片 ====================

def chunk_elements_by_title(raw_elements: List[Any]) -> List[Any]:
    """
    使用 Unstructured 官方 chunk_by_title。

    overlap 行为（默认）：
    - overlap=CHUNK_OVERLAP：仅在同一段落（同一 Title 下）因超过 max_characters
      被硬切分时，相邻子块之间重叠。
    - overlap_all=False：不同 Title 之间不会 overlap，章节边界保持干净。
    """
    from unstructured.chunking.title import chunk_by_title

    cfg = _chunk_by_title_config()
    overlap_all = os.getenv('CHUNK_OVERLAP_ALL', 'false').lower() == 'true'

    return chunk_by_title(
        raw_elements,
        max_characters=cfg['max_characters'],
        new_after_n_chars=cfg['new_after_n_chars'],
        combine_text_under_n_chars=cfg['combine_text_under_n_chars'],
        overlap=cfg['overlap'],
        overlap_all=overlap_all,
        include_orig_elements=True,
    )


def separate_content_types(chunk: Any) -> Dict[str, Any]:
    """从 chunk 的 orig_elements 分离文本/表格/图片（对齐 ai.ipynb）"""
    content_data: Dict[str, Any] = {
        'text': str(chunk),
        'table': [],
        'image': [],
        'types': ['text'],
        'element_types': [],
    }

    orig_elements = getattr(getattr(chunk, 'metadata', None), 'orig_elements', None)
    if not orig_elements:
        return content_data

    for element in orig_elements:
        element_type = type(element).__name__
        category = getattr(element, 'category', element_type)
        if category not in content_data['element_types']:
            content_data['element_types'].append(category)

        if element_type == 'Table':
            content_data['types'].append('table')
            table_html = getattr(element, 'text_as_html', None) or str(element)
            content_data['table'].append(table_html)
        elif element_type == 'Image':
            meta = getattr(element, 'metadata', None)
            image_b64 = getattr(meta, 'image_base64', None) if meta else None
            if image_b64:
                content_data['types'].append('image')
                content_data['image'].append(image_b64)

    content_data['types'] = list(set(content_data['types']))
    return content_data


def _extract_page_numbers(chunk: Any, content_data: Dict[str, Any]) -> List[int]:
    pages = set()
    orig_elements = getattr(getattr(chunk, 'metadata', None), 'orig_elements', None) or []
    for element in orig_elements:
        meta = getattr(element, 'metadata', None)
        if meta and getattr(meta, 'page_number', None) is not None:
            pages.add(meta.page_number)
    if not pages and hasattr(chunk, 'metadata'):
        pn = getattr(chunk.metadata, 'page_number', None)
        if pn is not None:
            pages.add(pn)
    return sorted(pages)


def _build_element_id_map(element_dicts: List[Dict[str, Any]]) -> Dict[str, int]:
    """unstructured element_id -> 入库 element_index"""
    mapping: Dict[str, int] = {}
    for elem in element_dicts:
        meta = elem.get('metadata') or {}
        for key in ('element_id', 'id'):
            eid = meta.get(key)
            if eid is not None:
                mapping[str(eid)] = elem['index']
        # 部分版本把 id 放在顶层
        if elem.get('id') is not None:
            mapping[str(elem['id'])] = elem['index']
    return mapping


def _extract_element_ids(chunk: Any, element_id_map: Dict[str, int]) -> List[int]:
    ids: List[int] = []
    seen = set()
    orig_elements = getattr(getattr(chunk, 'metadata', None), 'orig_elements', None) or []
    for element in orig_elements:
        candidates = []
        eid = getattr(element, 'id', None)
        if eid is not None:
            candidates.append(str(eid))

        meta = {}
        if hasattr(element, 'metadata') and element.metadata is not None:
            if hasattr(element.metadata, 'to_dict'):
                meta = element.metadata.to_dict() or {}
            elif isinstance(element.metadata, dict):
                meta = element.metadata
        for key in ('element_id', 'id'):
            if meta.get(key) is not None:
                candidates.append(str(meta[key]))

        for candidate in candidates:
            mapped = element_id_map.get(candidate)
            if mapped is not None and mapped not in seen:
                seen.add(mapped)
                ids.append(mapped)
    return ids


def _document_title(filename: Optional[str]) -> str:
    """从上传文件名得到写入切片的文档标题（去路径、去扩展名）。"""
    if not filename:
        return ''
    base = os.path.basename(str(filename).replace('\\', '/')).strip()
    if not base:
        return ''
    stem, _ext = os.path.splitext(base)
    return (stem or base).strip()


def _prepend_doc_title(text: str, doc_title: str) -> str:
    text = (text or '').strip()
    title = (doc_title or '').strip()
    if not title:
        return text
    marker = f'[Document: {title}]'
    if text.startswith(marker):
        return text
    if not text:
        return marker
    return f'{marker}\n{text}'


def build_basic_chunk_records(
    unstructured_chunks: List[Any],
    element_id_map: Optional[Dict[str, int]] = None,
    doc_title: str = '',
) -> List[Dict[str, Any]]:
    """仅按标题切片构建记录（不做 LLM 增强），可立即入库供 Chunking Tab 回填。"""
    records: List[Dict[str, Any]] = []
    element_id_map = element_id_map or {}
    doc_title = (doc_title or '').strip()

    for chunk in unstructured_chunks:
        content_data = separate_content_types(chunk)
        raw_text = content_data['text'].strip()
        if not raw_text and not content_data['table'] and not content_data['image']:
            continue

        # 正文切片带上文章标题，便于检索时区分合同/文档
        titled_text = _prepend_doc_title(raw_text, doc_title)

        has_mixed = bool(content_data['table'] or content_data['image'])
        page_numbers = _extract_page_numbers(chunk, content_data)
        orig_elements = getattr(getattr(chunk, 'metadata', None), 'orig_elements', None) or []
        orig_count = len(orig_elements) or 1
        element_ids = _extract_element_ids(chunk, element_id_map)
        element_types = content_data['element_types'] or []
        content_types = content_data['types'] or ['text']

        # 若 orig_elements 没解析出类型，至少保留 content_types
        if not element_types:
            element_types = list(content_types)

        records.append({
            'chunk_index': len(records),
            'text': titled_text,
            'text_for_embedding': titled_text,
            'doc_title': doc_title,
            'enhanced_summary': '',
            'char_count': len(titled_text),
            'element_count': orig_count or 1,
            'element_ids': element_ids,
            'page_numbers': page_numbers,
            'content_types': content_types,
            'element_types': element_types,
            'has_mixed_content': has_mixed,
            # 增强阶段仍需要原始分离结果
            '_content_data': content_data,
        })

    return records


def enhance_chunk_records(
    records: List[Dict[str, Any]],
    progress_callback=None,
) -> List[Dict[str, Any]]:
    """对已切片记录做 LLM 增强；不改 char_count（保持增强前原文长度）。"""
    mode = _llm_enhance_mode()
    total = len(records)

    for idx, record in enumerate(records):
        content_data = record.get('_content_data') or {
            'text': record.get('text', ''),
            'table': [],
            'image': [],
            'types': record.get('content_types', ['text']),
            'element_types': record.get('element_types', []),
        }
        has_mixed = bool(record.get('has_mixed_content'))
        enhanced_summary = ''

        if mode == 'all' or (mode == 'mixed' and has_mixed):
            try:
                enhanced_summary = create_ai_enhanced_summary(
                    content_data.get('text', ''),
                    content_data.get('table', []),
                    content_data.get('image', []),
                )
                print(
                    f"  📝 [{idx + 1}/{total}] chunk enhanced "
                    f"(types={content_data.get('types')})"
                )
            except Exception as e:
                print(f"  ⚠️  [{idx + 1}/{total}] LLM 增强失败，使用原文: {e}")
                enhanced_summary = ''

        record['enhanced_summary'] = enhanced_summary
        record['text_for_embedding'] = _build_embedding_text(
            record.get('text', ''),
            enhanced_summary,
        )
        # char_count 保持增强前原文长度，供 Chunking avg 使用

        if progress_callback:
            progress_callback(idx + 1, total)

    return records


def build_chunk_records(
    unstructured_chunks: List[Any],
    element_id_map: Optional[Dict[str, int]] = None,
    progress_callback=None,
    doc_title: str = '',
) -> List[Dict[str, Any]]:
    """兼容旧调用：先基础切片再增强。"""
    records = build_basic_chunk_records(
        unstructured_chunks, element_id_map, doc_title=doc_title
    )
    return enhance_chunk_records(records, progress_callback=progress_callback)


def _normalize_llm_text(content: Any) -> str:
    """ChatTongyi / qwen-vl 常返回 list[{'text': ...}]，统一成纯文本。"""
    if content is None:
        return ''
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get('text')
                if text:
                    parts.append(str(text))
        return '\n'.join(parts).strip()
    return str(content).strip()


def _build_embedding_text(raw_text: str, enhanced_summary: Any) -> str:
    """检索用：原文 + 增强描述拼接，保证关键词与语义均可匹配"""
    raw_text = (raw_text or '').strip()
    enhanced_summary = _normalize_llm_text(enhanced_summary)
    if not enhanced_summary:
        return raw_text
    return f"{raw_text}\n\n[检索增强描述]\n{enhanced_summary}"


def _to_dashscope_image_item(image_b64: str) -> Optional[Dict[str, str]]:
    """构造 DashScope VL 接受的 image 项（不要用 OpenAI 的 image_url）。"""
    if not image_b64 or not isinstance(image_b64, str):
        return None
    raw = image_b64.strip()
    if not raw:
        return None
    if raw.startswith('data:image'):
        return {'image': raw}
    # unstructured 默认多为 jpeg；若已是 png base64 也可用 image/png
    mime = 'image/png' if raw.startswith('iVBOR') else 'image/jpeg'
    return {'image': f'data:{mime};base64,{raw}'}


def create_ai_enhanced_summary(text: str, tables: List[str], images: List[str]) -> str:
    """多模态 LLM 增强（DashScope qwen-vl 原生消息格式）"""
    from langchain_core.messages import HumanMessage
    from langchain_community.chat_models.tongyi import ChatTongyi

    model = os.getenv('DASHSCOPE_CHAT_MODEL', 'qwen-vl-max')
    chat = ChatTongyi(model=model)

    prompt_text = (
        "You are a helpful assistant that creates a searchable description for document "
        "content retrieval.\n\n"
        f"THE TEXT:\n{text}\n"
    )
    if tables:
        prompt_text += "\nTHE TABLES:\n"
        for i, table in enumerate(tables):
            prompt_text += f"Table {i + 1}: {table[:4000]}\n\n"

    prompt_text += """
YOUR TASK:
Generate a comprehensive, searchable description that covers:
1. Key facts, numbers, and data points from text and tables
2. Main topics and concepts discussed
3. Questions this content could answer
4. Visual content analysis (charts, diagrams, patterns in images)
5. Alternative search terms users might use
Make it detailed and searchable - prioritize findability over brevity.
SEARCHABLE DESCRIPTION:"""

    # DashScope MultiModalConversation 要求 content 项为 {text}/{image}，
    # 不能使用 OpenAI 风格的 type=image_url。
    message_content: List[Dict[str, Any]] = []
    max_images = int(os.getenv('LLM_ENHANCE_MAX_IMAGES', '3'))
    for image_b64 in images[:max_images]:
        item = _to_dashscope_image_item(image_b64)
        if item:
            message_content.append(item)
    message_content.append({'text': prompt_text})

    response = chat.invoke([HumanMessage(content=message_content)])
    return _normalize_llm_text(
        response.content if hasattr(response, 'content') else response
    )


# ==================== 入库 ====================

def count_element_types(elements: List[Dict]) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for elem in elements:
        elem_type = elem['type']
        stats[elem_type] = stats.get(elem_type, 0) + 1
    return stats


def save_elements_to_db(file_id: int, elements: List[Dict]) -> int:
    count = 0
    for elem in elements:
        DocumentElementModel.create_element(
            file_id=file_id,
            element_index=elem['index'],
            element_type=elem['type'],
            text_content=elem['text'],
            metadata=elem['metadata'],
        )
        count += 1
    return count


def save_chunks_to_db(file_id: int, chunks: List[Dict]) -> int:
    count = 0
    for chunk in chunks:
        DocumentChunkModel.create_chunk(
            file_id=file_id,
            chunk_index=chunk['chunk_index'],
            chunk_text=chunk['text'],
            char_count=chunk['char_count'],
            element_count=chunk['element_count'],
            element_ids=chunk['element_ids'],
            page_numbers=chunk['page_numbers'],
            content_types=chunk.get('content_types') or [],
            element_types=chunk.get('element_types') or [],
        )
        count += 1
    return count


# ==================== 向量化 ====================

def vectorize_and_store(
    file_id: int,
    user_id: int,
    chunks: List[Dict],
    progress_callback=None,
) -> int:
    from app.core.rag import embed_document

    expected_dim = int(os.getenv('MILVUS_EMBEDDING_DIM', '1024'))
    embedded_chunks: List[Dict[str, Any]] = []
    total = len(chunks)
    failed_chunks: List[int] = []

    print(f"🧮 开始向量化: 共 {total} 个切片, 目标维度={expected_dim}")

    for idx, chunk in enumerate(chunks):
        chunk_index = chunk['chunk_index']
        try:
            embed_input = chunk.get('text_for_embedding') or chunk['text']
            embedding = embed_document(embed_input)
            actual_dim = len(embedding)

            print(
                f"  ✅ [{idx + 1}/{total}] chunk_index={chunk_index} "
                f"dim={actual_dim} raw_chars={chunk.get('char_count', 0)} "
                f"mixed={chunk.get('has_mixed_content', False)}"
            )

            if actual_dim != expected_dim:
                print(
                    f"  ❌ [{idx + 1}/{total}] chunk_index={chunk_index} "
                    f"维度 {actual_dim} != {expected_dim}"
                )
                failed_chunks.append(chunk_index)
                continue

            embedded_chunks.append({
                'chunk_index': chunk_index,
                'embedding': embedding,
                'text': chunk['text'],
                'metadata': {
                    'file_id': file_id,
                    'doc_title': chunk.get('doc_title') or '',
                    'char_count': chunk['char_count'],
                    'element_count': chunk['element_count'],
                    'page_numbers': chunk['page_numbers'],
                    'content_types': chunk.get('content_types', []),
                    'element_types': chunk.get('element_types', []),
                    'has_enhanced_summary': bool(chunk.get('enhanced_summary')),
                },
            })

            if progress_callback:
                progress_callback(idx + 1, total)

        except Exception as e:
            print(f"  ❌ [{idx + 1}/{total}] chunk_index={chunk_index} 向量化失败: {e}")
            failed_chunks.append(chunk_index)

    print(
        f"🧮 向量化阶段完成: 成功={len(embedded_chunks)}, "
        f"失败={len(failed_chunks)}, 总计={total}"
    )

    if not embedded_chunks:
        raise RuntimeError(f"所有切片向量化均失败 (failed_chunks={failed_chunks})")

    inserted = milvus_service.insert_vectors(
        user_id=user_id,
        file_id=file_id,
        chunks=embedded_chunks,
    )

    for chunk in embedded_chunks:
        DocumentChunkModel.update_chunk_embedding_status(
            file_id=file_id,
            chunk_index=chunk['chunk_index'],
            vector_id=f"user_{user_id}_file_{file_id}_chunk_{chunk['chunk_index']}",
            is_embedded=True,
        )

    if failed_chunks:
        print(f"⚠️  以下切片未写入 Milvus: {failed_chunks}")

    return inserted
