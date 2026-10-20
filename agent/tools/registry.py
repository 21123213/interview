"""工具注册表：同步 execute + 异步 aexecute（按 exec_mode 分流）。

按 skill 组装本次请求可用的工具视图；后续新 skill 在 resolve_skills /
build_registry_for_skills 中扩展即可。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

from agent.skills.loader import resolve_skills
from agent.tools.base import BaseTool, ToolResult
from agent.tools.builtin import (
    CalculatorTool,
    EchoTool,
    GetTimeTool,
    IoPingTool,
)
from agent.tools.travel import register_travel_tools
from agent.tools.web_search import register_web_search_tools
from agent.tools.xhs_search import register_xhs_general_tools

logger = logging.getLogger("agent.tools.registry")


class ToolRegistry:
    """按名称索引工具。"""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return sorted(self._tools.keys())

    def openai_tool_definitions(self) -> List[dict]:
        """原生 function calling：传给 chat.completions tools 参数。"""
        defs: List[dict] = []
        for tool in self._tools.values():
            spec = tool.spec
            params = spec.parameters or {"type": "object", "properties": {}}
            defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": params,
                    },
                }
            )
        return defs

    def execute(self, name: str, arguments: dict) -> ToolResult:
        """同步执行（兼容旧路径；CLI 主路径已改用 aexecute）。"""
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                content=f"未知工具: {name}。可用: {', '.join(self.names())}",
            )
        return tool.safe_run(arguments)

    async def aexecute(self, name: str, arguments: dict) -> ToolResult:
        """异步执行：local → 线程池；io → await arun。"""
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                content=f"未知工具: {name}。可用: {', '.join(self.names())}",
            )
        return await tool.safe_arun(arguments)


def _register_core(reg: ToolRegistry) -> None:
    reg.register(CalculatorTool())
    reg.register(GetTimeTool())
    reg.register(EchoTool())
    reg.register(IoPingTool())
    register_web_search_tools(reg)


def _eager_import_travel_skill_modules() -> None:
    """预加载 travel_skill 工具模块，避免并行首调撞 Python _ModuleLock。"""
    import travel_skill.tools.culture  # noqa: F401
    import travel_skill.providers.bocha  # noqa: F401
    import travel_skill.providers.xhs  # noqa: F401


def build_registry_for_skills(skill_ids: Sequence[str]) -> ToolRegistry:
    """按已启用 skill 组装工具表。

    - 始终：core + web_search
    - travel：旅游整组 + xhs_search
    - 无 travel：仅通用 xhs_search（在有 XHS 目录时）
    """
    skills = {str(s).strip() for s in skill_ids if str(s).strip()}
    reg = ToolRegistry()
    _register_core(reg)
    if "travel" in skills:
        _eager_import_travel_skill_modules()
        register_travel_tools(reg)
    register_xhs_general_tools(reg)
    logger.info(
        "tool_registry skills=%s tools=%s",
        sorted(skills) or ["(none)"],
        reg.names(),
    )
    return reg


def build_registry_for_input(user_input: str) -> tuple[ToolRegistry, List[str]]:
    """根据用户输入解析 skill 并构建本次请求的工具视图。"""
    skill_ids = resolve_skills(user_input)
    return build_registry_for_skills(skill_ids), skill_ids


def build_default_registry() -> ToolRegistry:
    """兼容旧入口：默认按「非旅游」注册；自检可用 build_registry_for_skills(['travel'])。"""
    return build_registry_for_skills([])
