"""辅助工具函数"""
import os
import uuid
from pathlib import Path
from typing import Optional


def generate_uuid() -> str:
    """生成UUID"""
    return str(uuid.uuid4())


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return Path(filename).suffix.lower()


def generate_unique_filename(original_filename: str) -> str:
    """
    生成唯一的文件名
    :param original_filename: 原始文件名
    :return: 唯一文件名（UUID + 扩展名）
    """
    ext = get_file_extension(original_filename)
    return f"{generate_uuid()}{ext}"


def ensure_directory_exists(directory: str):
    """确保目录存在，不存在则创建"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def get_file_size(file_path: str) -> int:
    """获取文件大小（字节）"""
    return os.path.getsize(file_path)


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    :param size_bytes: 字节数
    :return: 格式化后的字符串（如 1.5MB）
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def is_allowed_file_type(filename: str, allowed_extensions: list) -> bool:
    """
    检查文件类型是否允许
    :param filename: 文件名
    :param allowed_extensions: 允许的扩展名列表（如 ['.txt', '.pdf']）
    :return: 是否允许
    """
    ext = get_file_extension(filename)
    return ext in allowed_extensions


def mask_phone(phone: str) -> str:
    """
    手机号脱敏
    :param phone: 手机号
    :return: 脱敏后的手机号（如 138****8000）
    """
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[-4:]}"
    return phone
