"""计划结构：Planner 产出 / Execute 消费。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class PlanStep:
    """计划中的一步工具调用。"""

    id: str
    tool: str
    input: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class Plan:
    """一次规划结果。"""

    thought: str = ""
    # execute: 执行 steps；final: 已有最终答案；invalid: 解析失败
    decision: str = "execute"
    steps: List[PlanStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    replan_reason: str = ""
    raw: str = ""
    parse_ok: bool = True
    error: str = ""

    def step_map(self) -> Dict[str, PlanStep]:
        return {s.id: s for s in self.steps}


@dataclass
class ReviewResult:
    """执行后评估：直接终答或要求重规划。"""

    decision: str = "final"  # final | replan
    final_answer: str = ""
    replan_reason: str = ""
    raw: str = ""
    parse_ok: bool = True
    error: str = ""


def _extract_json_obj(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    # 去掉 ```json 围栏
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


def parse_plan(text: str) -> Plan:
    """解析 Planner 的 JSON 输出。"""
    raw = (text or "").strip()
    plan = Plan(raw=raw)
    data = _extract_json_obj(raw)
    if not data:
        plan.parse_ok = False
        plan.decision = "invalid"
        plan.error = "无法解析规划 JSON"
        return plan

    plan.thought = str(data.get("thought") or "").strip()
    decision = str(data.get("decision") or "").strip().lower()
    if decision in ("final", "done", "answer"):
        plan.decision = "final"
        plan.final_answer = str(data.get("final_answer") or data.get("answer") or "").strip()
        if not plan.final_answer:
            plan.parse_ok = False
            plan.error = "decision=final 但缺少 final_answer"
        return plan

    if decision in ("replan",):
        plan.decision = "replan"
        plan.replan_reason = str(data.get("replan_reason") or "").strip()
        return plan

    # 默认 execute
    plan.decision = "execute"
    steps_raw = data.get("steps") or []
    if not isinstance(steps_raw, list) or not steps_raw:
        plan.parse_ok = False
        plan.error = "decision=execute 但 steps 为空"
        return plan

    steps: List[PlanStep] = []
    for i, item in enumerate(steps_raw):
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id") or f"s{i + 1}").strip()
        tool = str(item.get("tool") or item.get("name") or "").strip()
        inp = item.get("input") or item.get("arguments") or {}
        if not isinstance(inp, dict):
            inp = {"value": inp}
        deps = item.get("depends_on") or item.get("deps") or []
        if not isinstance(deps, list):
            deps = []
        deps = [str(d) for d in deps]
        if not tool:
            continue
        steps.append(PlanStep(id=sid, tool=tool, input=inp, depends_on=deps))

    if not steps:
        plan.parse_ok = False
        plan.error = "steps 中无有效工具调用"
        return plan

    plan.steps = steps
    # 校验 depends_on 引用
    ids = {s.id for s in steps}
    for s in steps:
        for d in s.depends_on:
            if d not in ids:
                plan.parse_ok = False
                plan.error = f"步骤 {s.id} 依赖未知 id={d}"
                return plan
    return plan


def parse_review(text: str) -> ReviewResult:
    """解析执行后评估 JSON。"""
    raw = (text or "").strip()
    review = ReviewResult(raw=raw)
    data = _extract_json_obj(raw)
    if not data:
        # 宽松：整段当最终答案
        review.decision = "final"
        review.final_answer = raw
        review.parse_ok = True
        return review

    decision = str(data.get("decision") or "final").strip().lower()
    if decision in ("replan", "retry", "need_replan"):
        review.decision = "replan"
        review.replan_reason = str(
            data.get("replan_reason") or data.get("reason") or ""
        ).strip()
        return review

    review.decision = "final"
    review.final_answer = str(
        data.get("final_answer") or data.get("answer") or ""
    ).strip()
    if not review.final_answer:
        review.parse_ok = False
        review.error = "缺少 final_answer"
    return review


def validate_plan_tools(plan: Plan, known_tools: Set[str]) -> List[str]:
    """返回非法工具名列表。"""
    bad = []
    for s in plan.steps:
        if s.tool not in known_tools:
            bad.append(s.tool)
    return bad


def plan_to_tool_calls(plan: Plan) -> List[Dict[str, Any]]:
    """调试用序列化。"""
    return [
        {
            "id": s.id,
            "tool": s.tool,
            "input": s.input,
            "depends_on": s.depends_on,
        }
        for s in plan.steps
    ]


@dataclass
class PlanExecutionStatus:
    """对照「本轮 Planner 计划」与执行结果的完成度（与 skill 无关）。

    status:
      - complete: 计划内每步都有成功结果 → 才允许质量评审 / final
      - failed: 有步骤失败或被跳过 → 禁止 final，应 replan
      - incomplete: 计划内仍有未出现在结果里的 step（异常兜底）
      - empty: 计划无步骤（不应进入执行后评审）
    """

    status: str  # complete | failed | incomplete | empty
    ok_ids: List[str] = field(default_factory=list)
    failed_ids: List[str] = field(default_factory=list)
    pending_ids: List[str] = field(default_factory=list)

    @property
    def allows_quality_final(self) -> bool:
        """仅 complete 时允许 Reviewer 给出 final。"""
        return self.status == "complete"

    def replan_reason(self) -> str:
        if self.status == "empty":
            return "计划无步骤，请重新规划。"
        if self.status == "incomplete":
            return (
                "计划尚未全部执行（未完成步骤: "
                + ", ".join(self.pending_ids)
                + "）。请继续规划并执行剩余步骤，不要直接给最终答案。"
            )
        if self.status == "failed":
            return (
                "计划内有步骤失败或被跳过: "
                + ", ".join(self.failed_ids)
                + "。请根据 Observation 修正参数或换步骤后重规划，禁止在未成功完成计划时 final。"
            )
        return ""


def plan_execution_status(
    plan: Plan,
    results: Any,
) -> PlanExecutionStatus:
    """用代码判断：计划里所有 step 是否都有成功结果。

    results: 可迭代项需有 call_id（或 id）与 ok；也支持 dict[id -> result]。
    不读取 skill、不检查工具白名单——只对照「这张 plan」。
    """
    if not plan.steps:
        return PlanExecutionStatus(status="empty")

    by_id: Dict[str, Any] = {}
    if isinstance(results, dict):
        by_id = dict(results)
    else:
        for r in results or []:
            cid = getattr(r, "call_id", None) or getattr(r, "id", None)
            if cid is None and isinstance(r, dict):
                cid = r.get("call_id") or r.get("id")
            if cid is None:
                continue
            by_id[str(cid)] = r

    ok_ids: List[str] = []
    failed_ids: List[str] = []
    pending_ids: List[str] = []
    for step in plan.steps:
        sid = step.id
        r = by_id.get(sid)
        if r is None:
            pending_ids.append(sid)
            continue
        ok = getattr(r, "ok", None)
        if ok is None and isinstance(r, dict):
            ok = r.get("ok")
        if ok:
            ok_ids.append(sid)
        else:
            failed_ids.append(sid)

    if pending_ids:
        return PlanExecutionStatus(
            status="incomplete",
            ok_ids=ok_ids,
            failed_ids=failed_ids,
            pending_ids=pending_ids,
        )
    if failed_ids:
        return PlanExecutionStatus(
            status="failed",
            ok_ids=ok_ids,
            failed_ids=failed_ids,
            pending_ids=[],
        )
    return PlanExecutionStatus(
        status="complete",
        ok_ids=ok_ids,
        failed_ids=[],
        pending_ids=[],
    )


def format_plan_for_review(plan: Plan) -> str:
    """给 Reviewer 看的计划摘要（不含大段 input，避免刷屏）。"""
    if not plan.steps:
        return "(无步骤)"
    lines = []
    for s in plan.steps:
        deps = ",".join(s.depends_on) if s.depends_on else "-"
        lines.append(f"- {s.id}: {s.tool} (depends_on={deps})")
    return "\n".join(lines)
