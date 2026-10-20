"""工具基础协议。

exec_mode 是运行时元数据（不进 LLM 的 Action Input）：
- local: 同步 run，由 registry 丢进线程池
- io: 优先 await arun（真异步 IO）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

ExecMode = Literal["local", "io"]


@dataclass
class ToolSpec:
    """工具对外描述。

    parameters: 业务参数 JSON Schema，经 registry 填入 API tools。
    exec_mode: 给运行时分流，不暴露给模型。
    """

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    exec_mode: ExecMode = "local"


@dataclass
class ToolResult:
    """工具执行结果。

    注意：不要把 attempt / 熔断状态放进给模型看的 content。
    """

    ok: bool
    content: str
    data: Optional[Any] = None


class BaseTool(ABC):
    """单个工具适配器。"""

    spec: ToolSpec

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult:
        """同步执行（local 工具的主实现；io 工具可作降级）。"""

    async def arun(self, **kwargs: Any) -> ToolResult:
        """异步执行。

        默认把同步 run 丢到线程池，避免堵事件循环。
        IO 工具应覆盖本方法，用 await httpx 等真异步实现。
        """
        import asyncio

        return await asyncio.to_thread(self.run, **kwargs)

    def safe_run(self, arguments: Dict[str, Any]) -> ToolResult:
        """同步安全封装。"""
        try:
            return self.run(**arguments)
        except TypeError as exc:
            return ToolResult(ok=False, content=f"参数错误: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                ok=False, content=f"工具执行失败: {type(exc).__name__}: {exc}"
            )

    async def safe_arun(self, arguments: Dict[str, Any]) -> ToolResult:
        """异步安全封装：按 exec_mode 选择 arun 或 to_thread(run)。"""
        import asyncio

        try:
            if self.spec.exec_mode == "io":
                return await self.arun(**arguments)
            # local：显式进线程池（即使默认 arun 也是 to_thread，这里语义更清晰）
            return await asyncio.to_thread(self.run, **arguments)
        except TypeError as exc:
            return ToolResult(ok=False, content=f"参数错误: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                ok=False, content=f"工具执行失败: {type(exc).__name__}: {exc}"
            )
