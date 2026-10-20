"""一次 Agent 运行的结果结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentRunResult:
    """一次用户问题的运行结果。"""

    answer: str
    session_id: str
    trace_id: str
    steps: int = 0
    # ok / error / max_steps / needs_input
    status: str = "ok"
    error: str = ""
    user_input: str = ""
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    pending: Optional[Dict[str, Any]] = None
    trace_tree: Optional[Dict[str, Any]] = None
