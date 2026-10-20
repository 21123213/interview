"""多工具执行器：无依赖并行 gather，有依赖按拓扑层执行。

两条入口：
- run_calls：ReAct 多 Action，彼此无依赖，可并行
- run_plan：Plan-Execute，按 depends_on 分层，同层并行

缺参时（调用前或执行后）都会 needs_input=True + gaps，交给上层挂起追问。
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from agent.observability.metrics import get_metrics
from agent.observability.tracer import Span, get_tracer
from agent.resilience.circuit_breaker import CircuitOpenError
from agent.resilience.retry import RetryPolicy, call_with_retry_async
from agent.runtime.param_check import (
    ParamGap,
    UPSTREAM_PARAM_FIELDS,
    build_gaps_for_calls,
    gaps_from_failed_tool_results,
    is_empty_value,
    is_missing_params_content,
    parse_tool_error_payload,
)
from agent.runtime.plan_schema import Plan, PlanStep
from agent.runtime.tool_calls import ToolCallSpec, format_observations
from agent.tools.registry import ToolRegistry

logger = logging.getLogger("agent.runtime.tool_executor")

# 上游工具成功结果 → 下游参数自动灌入（plan 的 depends_on 只管顺序，不管数据）
_INJECT_FROM_TOOL: Dict[str, List[str]] = {
    "build_route": ["daily_routes"],
    "search_stay": ["hotel", "daily_routes"],
}

_TEMPLATE_REF = re.compile(r"^\{\{(\w+)\.([\w.]+)\}\}$")


@dataclass
class ToolExecResult:
    """单次工具调用的执行结果。"""

    call_id: str
    tool: str
    ok: bool
    content: str  # 成功时的观察文本，或失败时的错误说明
    arguments: Dict[str, Any] = field(default_factory=dict)
    error_class: str = ""  # 如 MissingParams / CircuitOpen / UnknownTool
    latency_ms: float = 0.0
    exec_mode: str = ""  # 工具声明的执行模式（来自 tool.spec）


@dataclass
class BatchExecResult:
    """一批（或一层计划）工具调用的汇总结果。"""

    results: List[ToolExecResult] = field(default_factory=list)
    observation_text: str = ""  # 拼好的观察文本，喂给 LLM
    any_failed: bool = False
    needs_input: bool = False  # True → 上层应挂起并向用户追问
    gaps: List[ParamGap] = field(default_factory=list)  # 缺哪些参
    # plan 模式：已完成步骤（resume 时可传入，避免重跑）
    completed: Dict[str, ToolExecResult] = field(default_factory=dict)


def _gaps_from_exec_results(
    registry: ToolRegistry,
    calls: Sequence[ToolCallSpec],
    results: Sequence[ToolExecResult],
    *,
    before_exec: bool,
) -> List[ParamGap]:
    """从执行结果里筛出「缺参」类失败，再转成 ParamGap。

    判定：error_class == MissingParams，或 content 命中缺参文案。
    before_exec=False 表示这是执行后发现的缺参（工具返回了缺参错误）。
    即使 schema required 已齐（如 build_route 缺 itinerary_lines），也会生成 gap。
    """
    return gaps_from_failed_tool_results(
        registry, list(calls), list(results), before_exec=before_exec
    )


def _parse_ok_payload(result: ToolExecResult) -> Optional[Dict[str, Any]]:
    """解析成功工具的 JSON content；失败或不像 JSON 则 None。"""
    if not result.ok:
        return None
    data = parse_tool_error_payload(result.content)
    if data is None or not data.get("ok", True):
        return None
    return data


def _lookup_path(data: Dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _daily_routes_from_payload(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 build_route / 已有 daily_routes 载荷抽出 {days:[...]}。"""
    if isinstance(data.get("daily_routes"), dict):
        dr = data["daily_routes"]
        if dr.get("days"):
            return dr
    days = data.get("days")
    if isinstance(days, list) and days:
        return {"days": days}
    return None


def _inject_value_for_field(field: str, data: Dict[str, Any]) -> Any:
    if field == "daily_routes":
        return _daily_routes_from_payload(data)
    if field == "hotel":
        hotel = data.get("hotel")
        return hotel if isinstance(hotel, dict) else None
    val = data.get(field)
    return None if is_empty_value(val) else val


def inject_upstream_args(
    step: PlanStep,
    done: Dict[str, ToolExecResult],
) -> Dict[str, Any]:
    """把依赖步骤的成功输出灌进当前 step.input（原地改，并返回新 dict）。

    - 解析 {{sid.field}} 模板
    - 对 UPSTREAM_PARAM_FIELDS：按依赖工具类型自动填充（build_route→daily_routes 等）
    """
    merged = dict(step.input or {})

    # 1) {{s1.date}} / {{s7.days}} 模板
    for key, val in list(merged.items()):
        if not isinstance(val, str):
            continue
        m = _TEMPLATE_REF.match(val.strip())
        if not m:
            continue
        sid, path = m.group(1), m.group(2)
        upstream = done.get(sid)
        if upstream is None:
            continue
        payload = _parse_ok_payload(upstream)
        if payload is None:
            continue
        looked = _lookup_path(payload, path)
        if not is_empty_value(looked):
            merged[key] = looked

    # 2) 旅游上游产物：缺啥补啥
    for dep_id in step.depends_on:
        upstream = done.get(dep_id)
        if upstream is None or not upstream.ok:
            continue
        payload = _parse_ok_payload(upstream)
        if payload is None:
            continue
        for field in _INJECT_FROM_TOOL.get(upstream.tool, []):
            if field not in UPSTREAM_PARAM_FIELDS and field != "hotel":
                continue
            if not is_empty_value(merged.get(field)):
                continue
            injected = _inject_value_for_field(field, payload)
            if not is_empty_value(injected):
                merged[field] = injected
                logger.info(
                    "inject_upstream step=%s from=%s(%s) field=%s",
                    step.id,
                    dep_id,
                    upstream.tool,
                    field,
                )

    step.input = merged
    return merged


def _chunked(items: List[Any], size: int) -> List[List[Any]]:
    """按 size 切成若干批，供并行 gather 时限制并发数。"""
    if size <= 0:
        size = 1
    return [items[i : i + size] for i in range(0, len(items), size)]


class ToolExecutor:
    """共享执行层：ReAct 多 Action 与 Plan-Execute 共用。

    retry：失败重试策略；max_parallel：单批最大并发。
    """

    def __init__(
        self,
        tools: ToolRegistry,
        *,
        retry: Optional[RetryPolicy] = None,
        max_parallel: int = 6,
    ) -> None:
        self.tools = tools
        self.retry = retry or RetryPolicy()
        self.max_parallel = max(1, max_parallel)

    async def run_calls(self, calls: Sequence[ToolCallSpec]) -> BatchExecResult:
        """无依赖批量执行：全部可并行（受 max_parallel 限制分批 gather）。

        流程：
        1. 调用前校验缺参 → 有 gap 直接 needs_input，不执行
        2. 分批 asyncio.gather 并行跑
        3. 拼 observation；若执行后仍报缺参，再标 needs_input
        """
        if not calls:
            return BatchExecResult(observation_text="(无工具调用)")

        # 执行前缺参检查：缺了就不浪费调用
        gaps = build_gaps_for_calls(self.tools, list(calls), before_exec=True)
        if gaps:
            return BatchExecResult(
                observation_text="(调用前缺参，尚未执行)",
                needs_input=True,
                gaps=gaps,
            )

        results: List[ToolExecResult] = []
        with get_tracer().span(
            "tools.batch", count=len(calls), mode="parallel"
        ) as batch_span:
            for batch in _chunked(list(calls), self.max_parallel):
                get_metrics().incr("tool_batch_total", mode="parallel", size=str(len(batch)))
                parts = await asyncio.gather(
                    *[self._run_one(c, parent_span=batch_span) for c in batch],
                    return_exceptions=False,
                )
                results.extend(parts)

        any_failed = any(not r.ok for r in results)
        obs = format_observations(
            [
                {"call_id": r.call_id, "tool": r.tool, "content": r.content}
                for r in results
            ]
        )
        # 工具业务层也可能返回「缺参」文案，再转成 gap
        post_gaps = _gaps_from_exec_results(
            self.tools, list(calls), results, before_exec=False
        )
        return BatchExecResult(
            results=results,
            observation_text=obs,
            any_failed=any_failed,
            needs_input=bool(post_gaps),
            gaps=post_gaps,
        )

    async def run_plan(
        self,
        plan: Plan,
        *,
        completed: Optional[Dict[str, ToolExecResult]] = None,
    ) -> BatchExecResult:
        """按 depends_on 拓扑分层执行；同层并行。

        方案 B：某一层缺参时立刻停下，保留已完成步骤（completed），
        resume 时可把 completed 传回来，跳过已跑步骤。

        主循环每轮：
        1. 找出依赖已全部在 done 里的 ready 步骤
        2. 调用前缺参检查（含上游失败 → upstream_gap）
        3. 同层分批并行执行；执行后若缺参同样停下
        4. 环依赖 / 依赖永远不齐 → DependencyError 兜底
        """
        if not plan.steps:
            return BatchExecResult(observation_text="(计划无步骤)")

        remaining = {s.id: s for s in plan.steps}
        # resume：先灌入已完成结果，并从 remaining 剔除
        done: Dict[str, ToolExecResult] = dict(completed or {})
        order_results: List[ToolExecResult] = [done[s.id] for s in plan.steps if s.id in done]
        for sid in list(done.keys()):
            remaining.pop(sid, None)

        with get_tracer().span("tools.plan", steps=len(plan.steps)):
            safety = 0
            while remaining:
                safety += 1
                if safety > len(plan.steps) + 2:
                    # 环依赖兜底：剩余步骤全部标失败后退出
                    for sid, step in list(remaining.items()):
                        order_results.append(
                            ToolExecResult(
                                call_id=sid,
                                tool=step.tool,
                                ok=False,
                                content="计划依赖无法满足（可能存在环）",
                                arguments=step.input,
                                error_class="DependencyError",
                            )
                        )
                    remaining.clear()
                    break

                # 依赖都已完成 → 本层可跑
                ready: List[PlanStep] = []
                for sid, step in remaining.items():
                    if all(d in done for d in step.depends_on):
                        ready.append(step)

                if not ready:
                    # 有剩余但无人可跑（依赖失败或环），全部跳过
                    for sid, step in list(remaining.items()):
                        order_results.append(
                            ToolExecResult(
                                call_id=sid,
                                tool=step.tool,
                                ok=False,
                                content="依赖未就绪，跳过",
                                arguments=step.input,
                                error_class="DependencyError",
                            )
                        )
                        done[sid] = order_results[-1]
                    remaining.clear()
                    break

                # depends_on 只保证顺序：执行前把上游成功输出灌进下游 input
                for s in ready:
                    inject_upstream_args(s, done)

                # 上游失败的 id 传给缺参检查，用于 upstream_gap
                failed_up = {k for k, v in done.items() if not v.ok}
                gap_calls = [
                    ToolCallSpec(
                        name=s.tool,
                        arguments=s.input,
                        call_id=s.id,
                        depends_on=list(s.depends_on),
                    )
                    for s in ready
                ]
                gaps = build_gaps_for_calls(
                    self.tools,
                    gap_calls,
                    before_exec=True,
                    failed_upstream_ids=failed_up,
                )
                if gaps:
                    # 本层缺参：停住，把已完成的交给上层挂起
                    obs = format_observations(
                        [
                            {"call_id": r.call_id, "tool": r.tool, "content": r.content}
                            for r in order_results
                        ]
                    )
                    return BatchExecResult(
                        results=order_results,
                        observation_text=obs or "(本层缺参，尚未执行)",
                        any_failed=any(not r.ok for r in order_results),
                        needs_input=True,
                        gaps=gaps,
                        completed=done,
                    )

                get_metrics().incr(
                    "tool_batch_total", mode="plan_level", size=str(len(ready))
                )
                with get_tracer().span(
                    "tools.plan_level", size=len(ready)
                ) as level_span:
                    for batch in _chunked(ready, self.max_parallel):
                        calls = [
                            ToolCallSpec(
                                name=s.tool,
                                arguments=s.input,
                                call_id=s.id,
                                depends_on=list(s.depends_on),
                            )
                            for s in batch
                        ]
                        parts = await asyncio.gather(
                            *[
                                self._run_one(c, parent_span=level_span)
                                for c in calls
                            ]
                        )
                        for p in parts:
                            done[p.call_id] = p
                            order_results.append(p)
                            remaining.pop(p.call_id, None)
                        # 执行后缺参：同样停在本层；completed 里去掉 MissingParams 项
                        post_gaps = _gaps_from_exec_results(
                            self.tools, calls, parts, before_exec=False
                        )
                        if post_gaps:
                            obs = format_observations(
                                [
                                    {
                                        "call_id": r.call_id,
                                        "tool": r.tool,
                                        "content": r.content,
                                    }
                                    for r in order_results
                                ]
                            )
                            return BatchExecResult(
                                results=order_results,
                                observation_text=obs,
                                any_failed=True,
                                needs_input=True,
                                gaps=post_gaps,
                                completed={
                                    k: v
                                    for k, v in done.items()
                                    if v.error_class != "MissingParams"
                                },
                            )

        any_failed = any(not r.ok for r in order_results)
        obs = format_observations(
            [
                {"call_id": r.call_id, "tool": r.tool, "content": r.content}
                for r in order_results
            ]
        )
        return BatchExecResult(
            results=order_results,
            observation_text=obs,
            any_failed=any_failed,
            completed=done,
        )

    async def _run_one(
        self,
        call: ToolCallSpec,
        *,
        parent_span: Optional[Any] = None,
    ) -> ToolExecResult:
        """执行单个工具：查注册表 → 带重试调用 → 记指标 / 归类错误。

        错误分支：
        - 未知工具 → UnknownTool
        - 熔断打开 → CircuitOpen（友好文案，不抛给上层）
        - 其它异常 → error_class=异常类名
        - 业务失败且 content 像缺参 → MissingParams（供上层追问）

        parent_span: 并行批次父 span；传入时子 span 不压栈，避免兄弟节点串成父子。
        """
        tool_name = call.name
        arguments = call.arguments or {}
        call_id = call.call_id or tool_name
        dep = f"tool:{tool_name}"  # 重试/熔断按工具维度隔离
        tool = self.tools.get(tool_name)
        exec_mode = tool.spec.exec_mode if tool else "unknown"
        parent: Optional[Span] = parent_span if isinstance(parent_span, Span) else None

        if tool is None:
            get_metrics().incr(
                "tool_calls_total",
                tool=tool_name,
                status="unknown",
                exec_mode=exec_mode,
            )
            return ToolExecResult(
                call_id=call_id,
                tool=tool_name,
                ok=False,
                content=f"未知工具: {tool_name}。可用: {', '.join(self.tools.names())}",
                arguments=arguments,
                error_class="UnknownTool",
                exec_mode=exec_mode,
            )

        async def _once():
            with get_tracer().span(
                "tool.call",
                parent=parent,
                use_stack=parent is None,
                tool=tool_name,
                call_id=call_id,
                exec_mode=exec_mode,
            ):
                return await self.tools.aexecute(tool_name, arguments)

        t0 = time.time()
        try:
            result = await call_with_retry_async(dep, _once, self.retry)
            latency_ms = (time.time() - t0) * 1000
            get_metrics().observe("tool_latency_ms", latency_ms, tool=tool_name)
            get_metrics().incr(
                "tool_calls_total",
                tool=tool_name,
                status="ok" if result.ok else "biz_error",
                exec_mode=exec_mode,
            )
            content = result.content if result.ok else f"工具返回错误: {result.content}"
            error_class = ""
            if not result.ok and is_missing_params_content(result.content):
                error_class = "MissingParams"
            return ToolExecResult(
                call_id=call_id,
                tool=tool_name,
                ok=result.ok,
                content=content,
                arguments=arguments,
                error_class=error_class,
                latency_ms=latency_ms,
                exec_mode=exec_mode,
            )
        except CircuitOpenError:
            # 熔断：不重试，直接友好失败
            get_metrics().incr(
                "tool_calls_total",
                tool=tool_name,
                status="circuit_open",
                exec_mode=exec_mode,
            )
            return ToolExecResult(
                call_id=call_id,
                tool=tool_name,
                ok=False,
                content="工具暂时不可用，请稍后再试或改用其他方法。",
                arguments=arguments,
                error_class="CircuitOpen",
                exec_mode=exec_mode,
            )
        except Exception as exc:  # noqa: BLE001
            get_metrics().incr(
                "tool_calls_total",
                tool=tool_name,
                status="error",
                exec_mode=exec_mode,
            )
            logger.exception("工具最终失败 tool=%s", tool_name)
            return ToolExecResult(
                call_id=call_id,
                tool=tool_name,
                ok=False,
                content=f"工具调用失败: {type(exc).__name__}",
                arguments=arguments,
                error_class=type(exc).__name__,
                exec_mode=exec_mode,
            )
