"""LLM 响应与 DashScope OpenAI 兼容（多模态）调用工具。"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from langchain_openai import ChatOpenAI

# 与 .env 中 DASHSCOPE_COMPATIBLE_BASE 对齐；未配置时用代理兼容端点
DEFAULT_COMPATIBLE_BASE = (
    'https://token-plan.maas.qianwenaiapi.com/compatible-mode/v1'
)


def compatible_base_url() -> str:
    return (
        os.getenv('DASHSCOPE_COMPATIBLE_BASE') or DEFAULT_COMPATIBLE_BASE
    ).rstrip('/')


def make_dashscope_chat(
    *,
    model: Optional[str] = None,
    temperature: float = 0.3,
    streaming: bool = False,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
) -> ChatOpenAI:
    """
    统一通过 OpenAI 兼容多模态端点调用通义（ChatOpenAI）。
    支持 qwen3.8-* / qwen-vl-* 等需走 compatible-mode 的模型。
    """
    resolved = (
        model
        or os.getenv('DASHSCOPE_ANSWER_MODEL')
        or os.getenv('DASHSCOPE_FAST_MODEL')
        or 'qwen-plus'
    ).strip()
    key = (api_key or os.getenv('DASHSCOPE_API_KEY') or '').strip() or 'missing'
    if timeout is None:
        timeout = float(os.getenv('DASHSCOPE_TIMEOUT_SEC', '90'))
    return ChatOpenAI(
        model=resolved,
        api_key=key,
        base_url=compatible_base_url(),
        temperature=temperature,
        streaming=streaming,
        timeout=timeout,
        max_retries=1,
    )


def normalize_llm_text(content: Any) -> str:
    """将 ChatOpenAI / ChatTongyi / VL 的 str 或多模态 content 统一为纯文本。"""
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
                    continue
                # OpenAI 兼容: {"type":"text","text":"..."}
                if item.get('type') == 'text' and item.get('text'):
                    parts.append(str(item['text']))
        return '\n'.join(parts).strip()
    return str(content).strip()


def extract_stream_delta(chunk: Any) -> str:
    """从 LangChain stream chunk 提取增量文本。"""
    content = getattr(chunk, 'content', None)
    if content is None and isinstance(chunk, dict):
        content = chunk.get('content')
    if not content:
        return ''
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get('text')
                if text:
                    parts.append(str(text))
        return ''.join(parts)
    return str(content)


def to_openai_image_url_part(image_b64: str) -> Optional[Dict[str, Any]]:
    """构造 OpenAI 兼容多模态 content 中的 image_url 块。"""
    if not image_b64 or not isinstance(image_b64, str):
        return None
    raw = image_b64.strip()
    if not raw:
        return None
    if raw.startswith('data:image'):
        url = raw
    else:
        mime = 'image/png' if raw.startswith('iVBOR') else 'image/jpeg'
        url = f'data:{mime};base64,{raw}'
    return {'type': 'image_url', 'image_url': {'url': url}}


def to_dashscope_image_item(image_b64: str) -> Optional[Dict[str, str]]:
    """旧版 DashScope 原生 {image: data:...}（兼容遗留调用）。"""
    if not image_b64 or not isinstance(image_b64, str):
        return None
    raw = image_b64.strip()
    if not raw:
        return None
    if raw.startswith('data:image'):
        return {'image': raw}
    mime = 'image/png' if raw.startswith('iVBOR') else 'image/jpeg'
    return {'image': f'data:{mime};base64,{raw}'}


def multimodal_user_content(
    text: str,
    images_b64: Optional[List[str]] = None,
) -> Union[str, List[Dict[str, Any]]]:
    """
    组装 OpenAI 兼容多模态 user content。
    无图时返回纯字符串；有图时返回 [text, image_url, ...] 列表。
    """
    images_b64 = images_b64 or []
    parts: List[Dict[str, Any]] = []
    if text:
        parts.append({'type': 'text', 'text': text})
    for img in images_b64:
        item = to_openai_image_url_part(img)
        if item:
            parts.append(item)
    if not parts:
        return text or ''
    if len(parts) == 1 and parts[0].get('type') == 'text':
        return text
    return parts
