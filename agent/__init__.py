"""Agent 运行时包（与 backend RAG 平级，非 LangChain）。

子模块：
- observability: 日志 / tracing / 指标
- resilience: 重试 / 指数退避 / 熔断（细节不进 Agent Observation）
- models: 多模型抽象与 fast/strong 路由
- memory: 会话记忆（全量存储；进 prompt 为近窗骨架 + 摘要）
- tools: 工具协议与内置演示工具
- runtime: ReAct 主循环
- main_agent: 门面组装
- cli: 终端调试
"""

__version__ = "0.1.0"

from agent.main_agent import MainAgent

__all__ = ["MainAgent", "__version__"]
