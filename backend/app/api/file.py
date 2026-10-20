"""文件上传相关API"""
import asyncio
import os
import uuid
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional
from app.schemas.file import (
    FileUploadResponse, FileListResponse, FileMetadataResponse,
    FileProcessResponse, BatchDeleteRequest, BatchDeleteResponse,
)
from app.schemas.user import MessageResponse
from app.models.file import FileMetadataModel, FileContentModel
from app.core.security import get_current_user
from app.core.rag import rag_service
from app.utils.helpers import (
    generate_unique_filename, get_file_extension,
    ensure_directory_exists, is_allowed_file_type
)

router = APIRouter(prefix="/api/files", tags=["文件管理"])


def _purge_user_file(user_id: int, file_info: dict, *, bump_corpus: bool = True) -> None:
    """删除单个文件：磁盘 → Milvus → Redis → DB（级联 chunks/elements）。

    bump_corpus: 默认 True，抬升 user corpus_ver 使 rag:qa 缓存失效。
    批量删除时可先 False，最后统一 bump 一次，避免反复 INCR。
    """
    file_id = int(file_info['id'])
    file_path = file_info.get('file_path') or ''
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            print(f"⚠️  删除本地文件失败 file_id={file_id}: {e}")

    try:
        from app.core.milvus_service import milvus_service
        milvus_service.delete_by_file(user_id, file_id)
    except Exception as e:
        print(f"⚠️  删除向量失败 file_id={file_id}: {e}")

    try:
        from app.core.redis_manager import redis_manager
        redis_manager.release_file_lock(file_id)
        redis_manager.clear_task_progress(file_id)
    except Exception as e:
        print(f"⚠️  清理缓存失败 file_id={file_id}: {e}")

    FileMetadataModel.delete_file(file_id)

    if bump_corpus:
        try:
            from app.core.qa_cache import bump_corpus_version
            bump_corpus_version(user_id)
        except Exception as e:
            print(f"⚠️  bump corpus_ver 失败 user_id={user_id}: {e}")


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """上传文件"""
    user_id = current_user['id']
    
    # 检查文件类型
    allowed_extensions = os.getenv('UPLOAD_ALLOWED_EXTENSIONS', '.txt,.pdf,.docx,.md').split(',')
    if not is_allowed_file_type(file.filename, allowed_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型，仅支持: {', '.join(allowed_extensions)}"
        )
    
    # 检查文件大小
    content = await file.read()
    file_size = len(content)
    max_size = int(os.getenv('UPLOAD_MAX_FILE_SIZE', '10485760'))  # 10MB
    
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（{max_size / 1024 / 1024}MB）"
        )
    
    # 生成唯一文件名
    original_filename = file.filename
    unique_filename = generate_unique_filename(original_filename)
    file_type = get_file_extension(original_filename)
    
    # 保存文件到本地（可选）
    upload_dir = os.getenv('UPLOAD_DIRECTORY', 'uploads')
    ensure_directory_exists(upload_dir)
    file_path = os.path.join(upload_dir, unique_filename)
    
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # 保存文件元数据到数据库
    FileMetadataModel.create_file_metadata(
        user_id=user_id,
        filename=unique_filename,
        original_filename=original_filename,
        file_path=file_path,
        file_size=file_size,
        file_type=file_type,
        mime_type=file.content_type or 'application/octet-stream'
    )
    
    # 注意：create_file_metadata 可能不返回正确的 file_id
    # 需要通过唯一文件名查询获取 file_id
    sql = f"SELECT id FROM file_metadata WHERE user_id = {user_id} AND filename = '{unique_filename}' ORDER BY id DESC "
    from app.database import query
    result = query(sql)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件创建失败，无法获取文件ID"
        )
    file_id = result[0]['id']
    
    # 保存文件二进制内容到数据库
    # FileContentModel.save_file_content(file_id, content)
    
    # ===== 启动后台处理任务 =====
    from app.tasks.file_processing import process_file_background
    from app.core.redis_manager import redis_manager

    task_id = str(uuid.uuid4())
    lock_acquired = redis_manager.acquire_file_lock(file_id, task_id, ttl=600)

    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该文件正在处理中，请稍后再试"
        )

    redis_manager.set_task_progress(
        file_id=file_id,
        status='pending',
        progress=0,
        current_step='pending',
        message='任务已提交，等待处理...'
    )

    async def _run_processing():
        try:
            await asyncio.to_thread(process_file_background, file_id, file_path, user_id)
        except Exception as e:
            print(f"❌ 后台处理任务失败 [file_id={file_id}]: {e}")

    asyncio.create_task(_run_processing())
    print(f"✅ 后台处理任务已启动: {task_id}")
    
    # 获取文件信息
    file_info = FileMetadataModel.get_file_by_id(file_id)
    
    return FileUploadResponse(
        file_id=file_info['id'],
        filename=file_info['filename'],
        original_filename=file_info['original_filename'],
        file_size=file_info['file_size'],
        upload_time=file_info['upload_time'],
        status=file_info['status']
    )


@router.get("/list", response_model=FileListResponse)
async def list_files(
    page: int = 1,
    size: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """获取用户文件列表"""
    user_id = current_user['id']
    
    # 获取文件列表
    files = FileMetadataModel.get_files_by_user(user_id, page, size)
    total = FileMetadataModel.count_user_files(user_id)
    
    # 转换为响应模型
    items = [
        FileMetadataResponse(
            id=f['id'],
            user_id=f['user_id'],
            filename=f['filename'],
            original_filename=f['original_filename'],
            file_path=f['file_path'],
            file_size=f['file_size'],
            file_type=f['file_type'],
            mime_type=f['mime_type'],
            status=f['status'],
            chunks_count=f['chunks_count'],
            error_message=f.get('error_message'),
            upload_time=f['upload_time'],
            processed_time=f.get('processed_time')
        )
        for f in files
    ]
    
    return FileListResponse(total=total, items=items)


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_files(
    body: BatchDeleteRequest,
    current_user: dict = Depends(get_current_user),
):
    """批量删除当前用户选中的文件。"""
    user_id = current_user['id']
    deleted = 0
    errors: list[str] = []
    seen = set()

    for file_id in body.file_ids:
        if file_id in seen:
            continue
        seen.add(file_id)
        file_info = FileMetadataModel.get_file_by_id(file_id)
        if not file_info:
            errors.append(f'{file_id}: 不存在')
            continue
        if file_info['user_id'] != user_id:
            errors.append(f'{file_id}: 无权删除')
            continue
        try:
            # 批量时先不 bump，删完统一抬升 corpus_ver 一次
            _purge_user_file(user_id, file_info, bump_corpus=False)
            deleted += 1
        except Exception as e:
            errors.append(f'{file_id}: {e}')

    try:
        from app.core.redis_manager import redis_manager
        redis_manager.invalidate_user_files_cache(user_id)
    except Exception:
        pass

    if deleted > 0:
        try:
            from app.core.qa_cache import bump_corpus_version
            bump_corpus_version(user_id)
        except Exception as e:
            print(f"⚠️  batch-delete bump corpus_ver 失败: {e}")

    failed = len(errors)
    return BatchDeleteResponse(
        success=failed == 0,
        deleted=deleted,
        failed=failed,
        message=f'删除完成：成功 {deleted}，失败 {failed}',
        errors=errors[:20],
    )


@router.post("/delete-all", response_model=BatchDeleteResponse)
async def delete_all_files(
    current_user: dict = Depends(get_current_user),
):
    """删除当前用户的全部文件。"""
    user_id = current_user['id']
    files = FileMetadataModel.get_files_by_user(user_id, page=1, size=100000)
    deleted = 0
    errors: list[str] = []

    for file_info in files:
        try:
            _purge_user_file(user_id, file_info, bump_corpus=False)
            deleted += 1
        except Exception as e:
            errors.append(f"{file_info.get('id')}: {e}")

    # 兜底清掉该用户全部向量（防止单文件删除遗漏）
    try:
        from app.core.milvus_service import milvus_service
        milvus_service.delete_by_user(user_id)
    except Exception as e:
        print(f"⚠️  delete_by_user 失败: {e}")

    try:
        from app.core.redis_manager import redis_manager
        redis_manager.invalidate_user_files_cache(user_id)
    except Exception:
        pass

    # 语料清空：统一 bump，失效该用户全部 rag:qa 缓存
    try:
        from app.core.qa_cache import bump_corpus_version
        bump_corpus_version(user_id)
    except Exception as e:
        print(f"⚠️  delete-all bump corpus_ver 失败: {e}")

    failed = len(errors)
    return BatchDeleteResponse(
        success=failed == 0,
        deleted=deleted,
        failed=failed,
        message=f'已清空：成功 {deleted}，失败 {failed}',
        errors=errors[:20],
    )


@router.get("/{file_id}", response_model=FileMetadataResponse)
async def get_file_detail(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """获取文件详情"""
    file_info = FileMetadataModel.get_file_by_id(file_id)
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该文件"
        )
    
    return FileMetadataResponse(**file_info)


@router.delete("/{file_id}", response_model=MessageResponse)
async def delete_file(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """删除文件"""
    file_info = FileMetadataModel.get_file_by_id(file_id)
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该文件"
        )

    _purge_user_file(current_user['id'], file_info)
    try:
        from app.core.redis_manager import redis_manager
        redis_manager.invalidate_user_files_cache(current_user['id'])
    except Exception as e:
        print(f"⚠️  清理用户文件缓存失败: {e}")
    
    return MessageResponse(
        success=True,
        message="文件删除成功"
    )


@router.get("/{file_id}/progress")
async def get_file_processing_progress(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    获取文件处理进度（实时）
    前端可以轮询此接口获取进度
    """
    from app.core.redis_manager import redis_manager
    
    # 检查文件权限
    file_info = FileMetadataModel.get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该文件"
        )
    
    # 从Redis读取实时进度
    progress_data = redis_manager.get_task_progress(file_id)
    
    if progress_data:
        return progress_data
    
    # Redis中没有，从数据库读取状态
    return {
        "status": file_info['status'],
        "progress": 100 if file_info['status'] in ('completed', 'processed') else 0,
        "current_step": file_info['status'],
        "message": {
            'pending': '等待处理',
            'processing': '处理中...',
            'processed': '处理完成',
            'completed': '处理完成',
            'failed': '处理失败'
        }.get(file_info['status'], '未知状态')
    }


@router.get("/{file_id}/status")
async def get_file_processing_status(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    获取文件处理的详细状态，包括partitioning、chunking、summarization数据
    """
    from app.core.redis_manager import redis_manager
    from app.models.document import DocumentElementModel, DocumentChunkModel
    
    # 检查权限
    file_info = FileMetadataModel.get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    
    # 从Redis获取实时进度
    progress_data = redis_manager.get_task_progress(file_id) or {}
    
    # 构建响应
    response = {
        "file_id": file_id,
        "filename": file_info['original_filename'],
        "status": progress_data.get("status", file_info['status']),
        "current_stage": progress_data.get("current_step"),
        "progress": progress_data.get("progress", 0)
    }
    
    # 获取partitioning数据
    try:
        elements = DocumentElementModel.get_elements_by_file(file_id)
        if elements:
            element_types = {}
            for elem in elements:
                elem_type = elem.get('element_type') or elem.get('type', 'unknown')
                element_types[elem_type] = element_types.get(elem_type, 0) + 1

            response["partitioning"] = {
                "total_elements": len(elements),
                "element_types": {
                    "text_sections": (
                        element_types.get('NarrativeText', 0)
                        + element_types.get('Text', 0)
                        + element_types.get('UncategorizedText', 0)
                    ),
                    "tables": element_types.get('Table', 0),
                    "images": (
                        element_types.get('Image', 0)
                        + element_types.get('FigureCaption', 0)
                    ),
                    "titles": element_types.get('Title', 0),
                    "list_items": (
                        element_types.get('ListItem', 0)
                        + element_types.get('List', 0)
                    ),
                }
            }
    except Exception as e:
        print(f"Error getting partitioning data: {e}")
    
    # 获取chunking数据
    chunks = []
    try:
        chunks = DocumentChunkModel.get_chunks_by_file(file_id)
        if chunks:
            total_chars = sum(chunk.get('char_count', 0) for chunk in chunks)
            avg_chunk_size = total_chars / len(chunks) if chunks else 0
            
            response["chunking"] = {
                "total_elements": len(elements) if elements else 0,
                "total_chunks": len(chunks),
                "avg_chunk_size": int(avg_chunk_size)
            }
    except Exception as e:
        print(f"Error getting chunking data: {e}")

    # summarization / embedding 进度（不依赖 chunks 是否已入库）
    try:
        step = progress_data.get("current_step")
        processed_raw = progress_data.get("processed_chunks", 0)
        try:
            processed = int(processed_raw or 0)
        except (TypeError, ValueError):
            processed = 0

        if file_info['status'] == 'processed':
            total = len(chunks) if chunks else processed
            response["summarization"] = {
                "total_chunks": total,
                "processed_chunks": total,
                "progress_percentage": 100
            }
        elif step in ("summarization", "embedding"):
            total = len(chunks) if chunks else max(processed, 1)
            response["summarization"] = {
                "total_chunks": total,
                "processed_chunks": processed,
                "progress_percentage": (processed / total * 100) if total else 0
            }
    except Exception as e:
        print(f"Error getting summarization data: {e}")
    
    return response


@router.get("/{file_id}/summarization-progress")
async def get_summarization_progress(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    获取向量化/总结的实时进度
    """
    from app.core.redis_manager import redis_manager
    from app.models.document import DocumentChunkModel
    
    # 检查权限
    file_info = FileMetadataModel.get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    
    # 获取总chunks数
    chunks = DocumentChunkModel.get_chunks_by_file(file_id)
    total_chunks = len(chunks)
    
    # 从Redis获取进度
    progress_data = redis_manager.get_task_progress(file_id) or {}
    
    if file_info['status'] == 'processed':
        return {
            "total_chunks": total_chunks,
            "processed_chunks": total_chunks,
            "progress_percentage": 100
        }
    
    processed_raw = progress_data.get("processed_chunks", 0)
    try:
        processed_chunks = int(processed_raw or 0)
    except (TypeError, ValueError):
        processed_chunks = 0

    total = total_chunks if total_chunks > 0 else max(processed_chunks, 1)
    
    return {
        "total_chunks": total,
        "processed_chunks": processed_chunks,
        "progress_percentage": (processed_chunks / total * 100) if total > 0 else 0
    }


@router.get("/{file_id}/chunks")
async def get_file_chunks(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """获取文件的切片列表"""
    from app.models.document import DocumentChunkModel, DocumentElementModel
    
    # 检查权限
    file_info = FileMetadataModel.get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    
    # 获取切片与元素，用于还原 element_types
    chunks = DocumentChunkModel.get_chunks_by_file(file_id)
    elements = DocumentElementModel.get_elements_by_file(file_id) or []
    elem_by_index = {}
    for el in elements:
        idx = el.get('element_index')
        if idx is None:
            idx = el.get('index')
        if idx is not None:
            elem_by_index[int(idx)] = el

    normalized_chunks = []
    for chunk in chunks:
        page_numbers = chunk.get('page_numbers') or []
        raw_ids = chunk.get('element_ids') or []
        element_ids = [str(eid) for eid in raw_ids]
        element_count = chunk.get('element_count') or len(element_ids)

        # 优先用入库的类型；没有则从元素反查
        element_types = list(chunk.get('element_types') or [])
        content_types = list(chunk.get('content_types') or [])

        if not element_types:
            for eid in raw_ids:
                try:
                    el = elem_by_index.get(int(eid))
                except (TypeError, ValueError):
                    el = None
                if not el:
                    continue
                etype = el.get('element_type') or el.get('type')
                if etype and etype not in element_types:
                    element_types.append(etype)

        if not content_types:
            # 从 element_types 推导 content_types
            inferred = set()
            for et in element_types:
                if et in ('Table',):
                    inferred.add('table')
                elif et in ('Image', 'Figure', 'Picture'):
                    inferred.add('image')
                else:
                    inferred.add('text')
            content_types = list(inferred) or ['text']

        # 展示用主类型：多类型时用 mixed，否则用第一个 content type
        if len(content_types) > 1:
            chunk_type = 'mixed'
        elif content_types:
            chunk_type = content_types[0]
        else:
            chunk_type = chunk.get('chunk_type') or 'text'

        normalized_chunks.append({
            'id': str(chunk.get('id', '')),
            'content': chunk.get('chunk_text', ''),
            'element_ids': element_ids,
            'element_count': element_count,
            'character_count': chunk.get('char_count', 0),
            'page_number': page_numbers[0] if page_numbers else None,
            'chunk_type': chunk_type,
            'content_types': content_types,
            'metadata': {
                'filename': file_info.get('original_filename', ''),
                'page_number': page_numbers[0] if page_numbers else None,
                'element_types': element_types,
                'content_types': content_types,
            },
            'is_embedded': chunk.get('is_embedded', False),
        })

    return {
        "file_id": file_id,
        "total_chunks": len(normalized_chunks),
        "chunks": normalized_chunks
    }


@router.get("/{file_id}/elements")
async def get_file_elements(
    file_id: int,
    element_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """获取文件的元素列表"""
    from app.models.document import DocumentElementModel
    
    # 检查权限
    file_info = FileMetadataModel.get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    
    # 获取元素
    if element_type:
        elements = DocumentElementModel.get_elements_by_type(file_id, element_type)
    else:
        elements = DocumentElementModel.get_elements_by_file(file_id)
    
    return {
        "file_id": file_id,
        "total_elements": len(elements),
        "elements": elements
    }


@router.post("/{file_id}/process", response_model=FileProcessResponse)
async def process_file(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """手动触发文件处理（向量化）"""
    file_info = FileMetadataModel.get_file_by_id(file_id)
    
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限
    if file_info['user_id'] != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权处理该文件"
        )
    
    # 处理文件
    try:
        FileMetadataModel.update_file_status(file_id, 'processing')
        chunks_count = rag_service.process_file(file_info['file_path'], file_info['file_type'])
        FileMetadataModel.update_file_status(file_id, 'processed', chunks_count=chunks_count)
        
        return FileProcessResponse(
            file_id=file_id,
            status='processed',
            message='文件处理成功',
            chunks_count=chunks_count
        )
    except Exception as e:
        FileMetadataModel.update_file_status(file_id, 'failed', error_message=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件处理失败: {str(e)}"
        )
