"""内置演示工具。

- calculator / get_time / echo: exec_mode=local → 线程池
- io_ping: exec_mode=io → 真异步 await（模拟外界 IO，不依赖外网）
"""

from __future__ import annotations

import ast
import asyncio
import operator
import time
from datetime import datetime
from typing import Any

from agent.tools.base import BaseTool, ToolResult, ToolSpec

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    raise ValueError("仅支持数字与 + - * / ** % // 运算")


class CalculatorTool(BaseTool):
    """算术计算器（本地）。"""

    spec = ToolSpec(
        name="calculator",
        description="计算数学表达式，支持加减乘除与幂运算。例如 expression='(1+2)*3'",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"],
        },
        exec_mode="local",
    )

    def run(self, expression: str = "", **_: Any) -> ToolResult:
        if not expression or not str(expression).strip():
            return ToolResult(ok=False, content="缺少参数 expression")
        try:
            tree = ast.parse(str(expression).strip(), mode="eval")
            value = _eval_ast(tree)
            if isinstance(value, float) and value.is_integer():
                display: object = int(value)
            else:
                display = value
            return ToolResult(ok=True, content=str(display), data=value)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, content=f"计算失败: {exc}")


class GetTimeTool(BaseTool):
    """获取当前本地时间（本地）。"""

    spec = ToolSpec(
        name="get_time",
        description="获取当前本地日期时间，无需参数。",
        parameters={"type": "object", "properties": {}},
        exec_mode="local",
    )

    def run(self, **_: Any) -> ToolResult:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return ToolResult(ok=True, content=now, data={"ts": time.time()})


class EchoTool(BaseTool):
    """回声工具（本地）。"""

    spec = ToolSpec(
        name="echo",
        description="原样返回 text 内容，用于调试。",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        exec_mode="local",
    )

    def run(self, text: str = "", **_: Any) -> ToolResult:
        return ToolResult(ok=True, content=str(text), data=text)


class IoPingTool(BaseTool):
    """模拟外界 IO 的异步工具（演示 exec_mode=io）。

    用 asyncio.sleep 假装网络往返；真实项目里应换成 httpx/DB 等 await。
    """

    spec = ToolSpec(
        name="io_ping",
        description=(
            "模拟一次异步 IO 探测。可选参数 message（原样带回），"
            "delay_ms（等待毫秒，默认 50，上限 2000）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "可选回显文本"},
                "delay_ms": {
                    "type": "number",
                    "description": "模拟 IO 延迟毫秒，默认 50",
                },
            },
        },
        exec_mode="io",
    )

    def run(self, message: str = "pong", delay_ms: float = 50, **_: Any) -> ToolResult:
        # 同步降级：阻塞 sleep（一般走 arun，不走这里）
        delay = min(max(float(delay_ms), 0.0), 2000.0) / 1000.0
        time.sleep(delay)
        return ToolResult(
            ok=True,
            content=f"io_ping_ok message={message} delay_ms={int(delay * 1000)}",
            data={"message": message, "delay_ms": delay * 1000},
        )

    async def arun(
        self, message: str = "pong", delay_ms: float = 50, **_: Any
    ) -> ToolResult:
        delay = min(max(float(delay_ms), 0.0), 2000.0) / 1000.0
        await asyncio.sleep(delay)  # 真异步挂起，不占线程
        return ToolResult(
            ok=True,
            content=f"io_ping_ok message={message} delay_ms={int(delay * 1000)}",
            data={"message": message, "delay_ms": delay * 1000},
        )
