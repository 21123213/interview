"""工具协议与注册表（适配器层）。

exec_mode=local → 线程池；exec_mode=io → await arun。
Observation 只返回业务结果，不含重试细节。
"""

from agent.tools.base import BaseTool, ExecMode, ToolResult, ToolSpec
from agent.tools.registry import (
    ToolRegistry,
    build_default_registry,
    build_registry_for_input,
    build_registry_for_skills,
)

__all__ = [
    "BaseTool",
    "ExecMode",
    "ToolResult",
    "ToolSpec",
    "ToolRegistry",
    "build_default_registry",
    "build_registry_for_input",
    "build_registry_for_skills",
]
