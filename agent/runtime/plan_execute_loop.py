"""Plan-Execute 循环：规划 → 执行（并行/依赖）→ 评审 → 必要时重规划。

成本与收口（与 ReAct loop 对齐，映射到 PE 的 round）：
- max_replans：限制「规划轮次」
- RunBudget：限制累计 prompt_tokens + web_search 次数
触顶后强制 Reviewer 出 final，禁止继续 replan / 搜索。

「罐头文案」= 代码里写死的固定失败话术（如「已达到最大重规划次数…」），
不调用模型、不利用已有 Observation，用户几乎得不到可用答案。
本文件在触顶时改为强制综合，不再只返回罐头文案。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union

from agent.memory.base import MemoryRecord, MemoryStore
from agent.memory.windowed import SessionMemoryStore
from agent.models.base import ChatMessage, ChatModel
from agent.models.router import ModelRole, ModelRouter
from agent.observability.context import get_trace_id
from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer
from agent.prompts.planner import (
    build_planner_system_prompt,
    build_reviewer_system_prompt,
)
from agent.resilience.backoff import BackoffPolicy
from agent.resilience.retry import RetryPolicy, call_with_retry_async
from agent.runtime.budget import (
    RunBudgetConfig,
    RunBudgetState,
    load_run_budget_config,
)
from agent.runtime.needs_input import emit_needs_input
from agent.runtime.answer_parser import aparse_user_answers
from agent.runtime.pending import (
    PendingState,
    PendingStore,
    merge_answers_into_args,
)
from agent.runtime.plan_schema import (
    Plan,
    PlanExecutionStatus,
    PlanStep,
    format_plan_for_review,
    parse_plan,
    parse_review,
    plan_execution_status,
    plan_to_tool_calls,
    validate_plan_tools,
)
from agent.runtime.result import AgentRunResult
from agent.runtime.tool_executor import BatchExecResult, ToolExecResult, ToolExecutor
from agent.tools.registry import ToolRegistry

logger = logging.getLogger("agent.runtime.plan_execute")

# 软预算：提示 Planner 少搜，但仍允许本轮工具
_SOFT_BUDGET_PLANNER_HINT = (
    "【预算提示】本轮上下文消耗已较高：请尽量 decision=final；"
    "若必须 execute，禁止再规划 web_search，只用已有 Observation。"
)

# 硬收口：强制 Reviewer 给出 final（禁止 replan）
_FORCE_FINAL_REVIEW_HINT = (
    "【系统收口】禁止 decision=replan。必须输出 decision=final，"
    "基于已有 Observation 给出完整中文 final_answer；"
    "不确定处标注「以现场/官网为准」。不要要求再调用工具。"
)


def _serialize_completed(completed: Dict[str, ToolExecResult]) -> Dict[str, Any]:
    return {
        sid: {
            "call_id": r.call_id,
            "tool": r.tool,
            "ok": r.ok,
            "content": r.content,
            "arguments": r.arguments,
            "error_class": r.error_class,
            "latency_ms": r.latency_ms,
            "exec_mode": r.exec_mode,
        }
        for sid, r in completed.items()
    }


def _deserialize_completed(raw: Dict[str, Any]) -> Dict[str, ToolExecResult]:
    out: Dict[str, ToolExecResult] = {}
    for sid, item in (raw or {}).items():
        out[sid] = ToolExecResult(
            call_id=str(item.get("call_id") or sid),
            tool=str(item.get("tool") or ""),
            ok=bool(item.get("ok")),
            content=str(item.get("content") or ""),
            arguments=dict(item.get("arguments") or {}),
            error_class=str(item.get("error_class") or ""),
            latency_ms=float(item.get("latency_ms") or 0),
            exec_mode=str(item.get("exec_mode") or ""),
        )
    return out


def _plan_from_payload(raw: Dict[str, Any]) -> Plan:
    steps = []
    for item in raw.get("steps") or []:
        steps.append(
            PlanStep(
                id=str(item.get("id") or ""),
                tool=str(item.get("tool") or ""),
                input=dict(item.get("input") or {}),
                depends_on=[str(d) for d in (item.get("depends_on") or [])],
            )
        )
    return Plan(
        thought=str(raw.get("thought") or ""),
        decision=str(raw.get("decision") or "execute"),
        steps=steps,
        parse_ok=True,
    )


class PlanExecuteLoop:
    """Planner + Execute + Review（含重规划）。"""

    def __init__(
        self,
        *,
        router: ModelRouter,
        tools: ToolRegistry,
        memory: MemoryStore,
        max_replans: int = 2,
        max_parallel_tools: int = 5,
        llm_retry: Optional[RetryPolicy] = None,
        tool_retry: Optional[RetryPolicy] = None,
        pending_store: Optional[PendingStore] = None,
    ) -> None:
        self.router = router
        self.tools = tools
        self.memory = memory
        self.pending_store = pending_store or PendingStore()
        self.max_replans = max(0, max_replans)
        # 与 ReAct 共用同一套 env（AGENT_RUN_TOKEN_BUDGET / AGENT_WEB_SEARCH_MAX_PER_RUN）
        self.budget_cfg: RunBudgetConfig = load_run_budget_config()
        self.executor = ToolExecutor(
            tools,
            retry=tool_retry
            or RetryPolicy(
                max_attempts=3,
                backoff=BackoffPolicy(base_ms=200, factor=2.0, max_ms=4000),
            ),
            max_parallel=max_parallel_tools,
        )
        self.llm_retry = llm_retry or RetryPolicy(
            max_attempts=2,
            backoff=BackoffPolicy(base_ms=300, factor=2.0, max_ms=3000),
        )

    def run(self, user_input: str, session_id: str) -> AgentRunResult:
        return asyncio.run(self.arun(user_input, session_id))

    def _make_executor(self, tools: ToolRegistry) -> ToolExecutor:
        return ToolExecutor(
            tools,
            retry=self.executor.retry,
            max_parallel=self.executor.max_parallel,
        )

    async def aresume(
        self,
        session_id: str,
        answers: Any,
        pending: PendingState,
        *,
        tools: Optional[ToolRegistry] = None,
        skill_ids: Optional[List[str]] = None,
    ) -> AgentRunResult:
        """从暂停的计划层继续（合并用户补充后的 step.input）。

        upstream_gap：用户补充无法直接填满上游产物字段，改为带着 Observation
        与用户补充进入下一轮重规划，避免 `_continue` 空转死循环。
        """
        from agent.runtime.tool_calls import format_observations

        parsed = await aparse_user_answers(
            pending.questions, answers, self.router
        )
        payload = pending.payload
        tools = tools or self.tools
        skill_ids = list(
            skill_ids
            if skill_ids is not None
            else (payload.get("skill_ids") or [])
        )
        executor = self._make_executor(tools)
        plan = _plan_from_payload(dict(payload.get("plan") or {}))
        for step in plan.steps:
            step.input = merge_answers_into_args(
                step.input, pending.questions, parsed, step.id
            )
        completed = _deserialize_completed(dict(payload.get("completed") or {}))
        observations_history = list(payload.get("observations_history") or [])
        transcript = list(payload.get("transcript") or [])
        round_i = int(payload.get("round_i") or 0)
        replan_reason = str(payload.get("replan_reason") or "")
        user_input = pending.user_input
        self._run_user_input = user_input
        answer_text = (
            json.dumps(answers, ensure_ascii=False)
            if isinstance(answers, dict)
            else str(answers)
        )
        self.memory.append(
            session_id,
            MemoryRecord(
                role="user",
                content=answer_text,
                meta={"kind": "needs_input_answer"},
            ),
        )
        # resume 时尽量恢复预算；旧 pending 无 budget 字段则从 0 起算
        budget = self._budget_from_payload(payload)

        # 把挂起前已跑完的工具结果写进 Observation，供重规划使用
        if completed:
            partial_obs = format_observations(
                [
                    {
                        "call_id": r.call_id,
                        "tool": r.tool,
                        "content": r.content,
                    }
                    for r in completed.values()
                ]
            )
            if partial_obs and partial_obs not in observations_history:
                observations_history.append(partial_obs)

        if pending.source == "upstream_gap":
            observations_history.append(f"用户补充：{answer_text}")
            transcript.append(
                {
                    "phase": "resume_replan",
                    "source": "upstream_gap",
                    "answer_preview": answer_text[:200],
                }
            )
            planner_sys = build_planner_system_prompt(
                user_input, skill_ids=skill_ids
            )
            reviewer_sys = build_reviewer_system_prompt()
            return await self._arun_from_round(
                session_id=session_id,
                trace_id=get_trace_id(),
                user_input=user_input,
                transcript=transcript,
                observations_history=observations_history,
                replan_reason=(
                    f"上游步骤结果不足（曾缺参暂停）。用户补充：{answer_text}。"
                    "请根据已有 Observation 与用户补充，写出具体 itinerary_lines "
                    "或 loose_pois 再调用 build_route；search_stay/plan_transport "
                    "需带上 daily_routes（及 hotel）。"
                ),
                start_round=round_i + 1,
                planner_sys=planner_sys,
                reviewer_sys=reviewer_sys,
                tool_defs=tools.openai_tool_definitions(),
                known=set(tools.names()),
                tools=tools,
                executor=executor,
                skill_ids=skill_ids,
                budget=budget,
            )

        return await self._continue_after_plan(
            session_id=session_id,
            trace_id=get_trace_id(),
            user_input=user_input,
            plan=plan,
            completed=completed,
            observations_history=observations_history,
            transcript=transcript,
            round_i=round_i,
            replan_reason=replan_reason,
            tools=tools,
            executor=executor,
            skill_ids=skill_ids,
            budget=budget,
        )

    def _budget_from_payload(self, payload: Dict[str, Any]) -> RunBudgetState:
        """从 needs_input pending 恢复本轮预算累计。"""
        raw = dict(payload.get("budget") or {})
        return RunBudgetState(
            prompt_tokens=int(raw.get("prompt_tokens") or 0),
            completion_tokens=int(raw.get("completion_tokens") or 0),
            web_search_calls=int(raw.get("web_search_calls") or 0),
            soft_nudged=bool(raw.get("soft_nudged") or False),
        )

    def _budget_should_force(self, budget: RunBudgetState) -> tuple[bool, str]:
        """硬闸：token 或 web_search 触顶 → 必须收口，禁止再搜/再 replan。"""
        cfg = self.budget_cfg
        if budget.prompt_tokens >= cfg.hard_tokens:
            return True, "token_hard"
        if budget.web_search_calls >= cfg.web_search_max:
            return True, "web_search_max"
        return False, ""

    def _trim_plan_web_search(self, plan: Plan, budget: RunBudgetState) -> int:
        """执行前按配额裁掉多余 web_search 步（原地改 plan.steps）。

        返回被裁掉的步数。同时清理 depends_on 里指向已删步骤的依赖，
        避免图执行因缺节点卡住。
        """
        remaining = max(0, self.budget_cfg.web_search_max - budget.web_search_calls)
        kept: List[PlanStep] = []
        dropped_ids: set[str] = set()
        used = 0
        for step in plan.steps:
            if step.tool == "web_search":
                if used < remaining:
                    kept.append(step)
                    used += 1
                else:
                    dropped_ids.add(step.id)
            else:
                kept.append(step)
        for step in kept:
            step.depends_on = [d for d in step.depends_on if d not in dropped_ids]
        dropped_n = len(plan.steps) - len(kept)
        plan.steps = kept
        return dropped_n

    async def _force_finalize_review(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        observations_history: List[str],
        transcript: List[Dict[str, Any]],
        steps_count: int,
        reviewer_sys: str,
        budget: RunBudgetState,
        reason: str,
    ) -> AgentRunResult:
        """强制收口：用 Reviewer 综合已有 Observation，替代「罐头文案」。

        罐头文案 = 写死的失败句子（不调模型、不用工具结果），用户几乎拿不到答案。
        这里改为再调一次评审模型，要求 decision=final。
        """
        metrics = get_metrics()
        messages = self._reviewer_messages(
            reviewer_sys,
            user_input,
            observations_history,
            force_final=True,
        )
        rev_model = self.router.get(
            ModelRole.STRONG, route_reason=f"force_finalize:{reason}"
        )
        try:
            rev_out = await self._acall_llm(
                rev_model,
                messages,
                role=ModelRole.STRONG,
                route_reason=f"force_finalize:{reason}",
            )
            budget.add_llm_usage(rev_out.prompt_tokens, rev_out.completion_tokens)
        except Exception as exc:  # noqa: BLE001
            # 模型也挂了：用 Observation 原文兜底（仍比纯罐头失败句有用）
            logger.error("强制收口 Reviewer 失败: %s", exc)
            obs_text = "\n---\n".join(observations_history).strip()
            answer = (
                f"已达资源上限（{reason}），根据已收集资料整理如下：\n{obs_text}"
                if obs_text
                else (
                    f"已达资源上限（{reason}），且没有可用观察结果。"
                    "请缩小问题后重试。"
                )
            )
            transcript.append(
                {
                    "phase": "force_finalize",
                    "reason": reason,
                    "error": str(exc),
                    "budget": budget.snapshot(self.budget_cfg),
                    "final_answer": answer,
                }
            )
            self.memory.append(
                session_id,
                MemoryRecord(
                    role="assistant",
                    content=answer,
                    meta={"kind": "force_finalize", "reason": reason},
                ),
            )
            metrics.incr("plan_execute_force_finalize_total", reason=reason)
            return self._ok(answer, session_id, trace_id, steps_count, transcript)

        review = parse_review(rev_out.content)
        answer = (review.final_answer or rev_out.content or "").strip()
        if not answer:
            obs_text = "\n---\n".join(observations_history).strip()
            answer = (
                f"已达资源上限（{reason}），根据已收集资料：\n{obs_text}"
                if obs_text
                else f"已达资源上限（{reason}），未能整理出完整结论。"
            )
        transcript.append(
            {
                "phase": "force_finalize",
                "reason": reason,
                "raw": rev_out.content,
                "budget": budget.snapshot(self.budget_cfg),
                "final_answer": answer,
            }
        )
        self.memory.append(
            session_id,
            MemoryRecord(
                role="assistant",
                content=answer,
                meta={"kind": "final_answer", "force_reason": reason},
            ),
        )
        metrics.incr("plan_execute_force_finalize_total", reason=reason)
        metrics.incr("plan_execute_success_total")
        return self._ok(answer, session_id, trace_id, steps_count, transcript)

    async def arun(
        self,
        user_input: str,
        session_id: str,
        *,
        tools: Optional[ToolRegistry] = None,
        skill_ids: Optional[List[str]] = None,
    ) -> AgentRunResult:
        trace_id = get_trace_id()
        transcript: List[Dict[str, Any]] = []
        tools = tools or self.tools
        skill_ids = list(skill_ids or [])
        executor = self._make_executor(tools)

        transcript.append(
            {
                "phase": "tool_registry",
                "skills": skill_ids,
                "tools": tools.names(),
            }
        )
        logger.info(
            "plan_execute registry session=%s skills=%s tools=%s",
            session_id,
            skill_ids or ["(none)"],
            tools.names(),
        )

        self.memory.append(session_id, MemoryRecord(role="user", content=user_input))
        if isinstance(self.memory, SessionMemoryStore):
            await self.memory.compact(session_id)
        self._run_user_input = user_input

        # 本轮用户提问的预算状态（跨 replan round 累计）
        budget = RunBudgetState()
        return await self._arun_from_round(
            session_id=session_id,
            trace_id=trace_id,
            user_input=user_input,
            transcript=transcript,
            observations_history=[],
            replan_reason="",
            start_round=0,
            planner_sys=build_planner_system_prompt(user_input, skill_ids=skill_ids),
            reviewer_sys=build_reviewer_system_prompt(),
            tool_defs=tools.openai_tool_definitions(),
            known=set(tools.names()),
            tools=tools,
            executor=executor,
            skill_ids=skill_ids,
            budget=budget,
        )

    async def _continue_after_plan(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        plan: Plan,
        completed: Dict[str, ToolExecResult],
        observations_history: List[str],
        transcript: List[Dict[str, Any]],
        round_i: int,
        replan_reason: str,
        tools: ToolRegistry,
        executor: ToolExecutor,
        skill_ids: List[str],
        budget: RunBudgetState,
    ) -> AgentRunResult:
        """resume 入口：从当前 plan 的未完成步骤继续，再走 review / 可能重规划。"""
        reviewer_sys = build_reviewer_system_prompt()
        # 必须带 skill_ids，否则 resume 后旅游技能说明会丢
        planner_sys = build_planner_system_prompt(user_input, skill_ids=skill_ids)
        tool_defs = tools.openai_tool_definitions()
        known = set(tools.names())
        steps_count = round_i + 1

        with get_tracer().span(
            "plan_execute.resume",
            round=round_i,
            skills=",".join(skill_ids) or "(none)",
            tools=",".join(tools.names()),
        ):
            # resume 执行前同样裁剪超额 web_search
            dropped = self._trim_plan_web_search(plan, budget)
            if dropped:
                logger.info(
                    "resume 裁剪 web_search dropped=%s used=%s max=%s",
                    dropped,
                    budget.web_search_calls,
                    self.budget_cfg.web_search_max,
                )

            batch = await executor.run_plan(plan, completed=completed)
            if batch.needs_input and batch.gaps:
                # 挂起前固化已跑工具观察，避免 resume/replan 丢检索结果
                if batch.observation_text and batch.observation_text not in observations_history:
                    observations_history.append(batch.observation_text)
                return emit_needs_input(
                    session_id=session_id,
                    trace_id=trace_id,
                    mode="plan_execute",
                    gaps=batch.gaps,
                    user_input=user_input,
                    payload={
                        "plan": {
                            "thought": plan.thought,
                            "decision": plan.decision,
                            "steps": plan_to_tool_calls(plan),
                        },
                        "completed": _serialize_completed(batch.completed),
                        "observations_history": observations_history,
                        "round_i": round_i,
                        "replan_reason": replan_reason,
                        "transcript": transcript,
                        "skill_ids": skill_ids,
                        # 挂起时保存预算，resume 后继续累计（含 soft_nudged）
                        "budget": budget.snapshot(self.budget_cfg),
                    },
                    transcript=transcript,
                    steps=steps_count,
                    store=self.pending_store,
                )

            # 统计本批实际跑掉的 web_search
            n_ws = sum(1 for r in batch.results if r.tool == "web_search")
            if n_ws:
                budget.add_web_search(n_ws)

            obs = batch.observation_text
            observations_history.append(obs)
            transcript.append(
                {
                    "round": round_i,
                    "phase": "execute",
                    "any_failed": batch.any_failed,
                    "budget": budget.snapshot(self.budget_cfg),
                    "results": [
                        {
                            "id": r.call_id,
                            "tool": r.tool,
                            "ok": r.ok,
                            "content": r.content,
                            "exec_mode": r.exec_mode,
                        }
                        for r in batch.results
                    ],
                }
            )

            gated = await self._gate_and_review(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                plan=plan,
                batch=batch,
                observations_history=observations_history,
                transcript=transcript,
                round_i=round_i,
                steps_count=steps_count,
                reviewer_sys=reviewer_sys,
                budget=budget,
            )
            if isinstance(gated, AgentRunResult):
                return gated
            replan_reason = str(gated)

        # 重规划：从下一轮继续；budget 继续累计
        return await self._arun_from_round(
            session_id=session_id,
            trace_id=trace_id,
            user_input=user_input,
            transcript=transcript,
            observations_history=observations_history,
            replan_reason=replan_reason,
            start_round=round_i + 1,
            planner_sys=planner_sys,
            reviewer_sys=reviewer_sys,
            tool_defs=tool_defs,
            known=known,
            tools=tools,
            executor=executor,
            skill_ids=skill_ids,
            budget=budget,
        )

    async def _arun_from_round(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        transcript: List[Dict[str, Any]],
        observations_history: List[str],
        replan_reason: str,
        start_round: int,
        planner_sys: str,
        reviewer_sys: str,
        tool_defs: List[dict],
        known: set,
        tools: ToolRegistry,
        executor: ToolExecutor,
        skill_ids: List[str],
        budget: RunBudgetState,
    ) -> AgentRunResult:
        metrics = get_metrics()
        steps_count = start_round
        with get_tracer().span(
            "plan_execute.run",
            session_id=session_id,
            resume=True,
            skills=",".join(skill_ids) or "(none)",
            tools=",".join(tools.names()),
        ):
            for round_i in range(start_round, self.max_replans + 1):
                steps_count = round_i + 1
                # 进入新一轮前若已硬触顶，直接综合已有观察（不再 plan 新搜索）
                force, force_reason = self._budget_should_force(budget)
                if force and observations_history:
                    return await self._force_finalize_review(
                        session_id=session_id,
                        trace_id=trace_id,
                        user_input=user_input,
                        observations_history=observations_history,
                        transcript=transcript,
                        steps_count=steps_count,
                        reviewer_sys=reviewer_sys,
                        budget=budget,
                        reason=force_reason,
                    )

                result = await self._one_round(
                    session_id=session_id,
                    trace_id=trace_id,
                    user_input=user_input,
                    transcript=transcript,
                    observations_history=observations_history,
                    replan_reason=replan_reason,
                    round_i=round_i,
                    planner_sys=planner_sys,
                    reviewer_sys=reviewer_sys,
                    tool_defs=tool_defs,
                    known=known,
                    executor=executor,
                    skill_ids=skill_ids,
                    budget=budget,
                )
                if isinstance(result, AgentRunResult):
                    return result
                replan_reason = str(result)

            # 轮次用尽：强制综合，不再返回写死的「已达到最大重规划次数…」罐头文案
            metrics.incr("plan_execute_max_replan_total")
            return await self._force_finalize_review(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                observations_history=observations_history,
                transcript=transcript,
                steps_count=steps_count,
                reviewer_sys=reviewer_sys,
                budget=budget,
                reason="max_replans",
            )

    async def _one_round(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        transcript: List[Dict[str, Any]],
        observations_history: List[str],
        replan_reason: str,
        round_i: int,
        planner_sys: str,
        reviewer_sys: str,
        tool_defs: List[dict],
        known: set,
        executor: ToolExecutor,
        skill_ids: List[str],
        budget: RunBudgetState,
    ) -> Union[AgentRunResult, str]:
        """跑一轮 plan→execute→review。

        返回 AgentRunResult（结束）或 str（下一轮 replan_reason）。
        """
        metrics = get_metrics()
        with get_tracer().span("plan_execute.round", round=round_i):
            # 软预算：只提示一次，让 Planner 倾向 final / 停搜
            soft_hint = ""
            if (
                not budget.soft_nudged
                and budget.prompt_tokens >= self.budget_cfg.soft_tokens
            ):
                soft_hint = _SOFT_BUDGET_PLANNER_HINT
                budget.soft_nudged = True
                logger.info(
                    "PE 软预算触发 prompt_tokens=%s soft=%s",
                    budget.prompt_tokens,
                    self.budget_cfg.soft_tokens,
                )

            plan_messages = self._planner_messages(
                planner_sys,
                session_id,
                user_input,
                observations_history,
                replan_reason,
                soft_budget_hint=soft_hint,
            )
            model, role, reason = self.router.resolve_for_react(
                step_index=round_i + 1,
                force_strong=(round_i > 0),
            )
            try:
                llm_out = await self._acall_llm(
                    model,
                    plan_messages,
                    role=role,
                    route_reason=reason,
                    tools=tool_defs,
                )
                budget.add_llm_usage(llm_out.prompt_tokens, llm_out.completion_tokens)
            except Exception as exc:  # noqa: BLE001
                return self._fail(
                    f"规划模型调用失败: {exc}",
                    session_id,
                    trace_id,
                    round_i + 1,
                    transcript,
                )

            plan = parse_plan(llm_out.content)
            round_log: Dict[str, Any] = {
                "round": round_i,
                "phase": "plan",
                "model": llm_out.model,
                "raw": llm_out.content,
                "decision": plan.decision,
                "parse_ok": plan.parse_ok,
                "budget": budget.snapshot(self.budget_cfg),
            }
            self.memory.append(
                session_id,
                MemoryRecord(
                    role="assistant",
                    content=llm_out.content,
                    meta={"kind": "plan", "round": round_i},
                ),
            )
            if not plan.parse_ok:
                metrics.incr("plan_parse_error_total")
                transcript.append({**round_log, "error": plan.error or "规划解析失败"})
                # 最后一轮解析失败：有观察则强制综合，否则才报错
                if round_i >= self.max_replans:
                    if observations_history:
                        return await self._force_finalize_review(
                            session_id=session_id,
                            trace_id=trace_id,
                            user_input=user_input,
                            observations_history=observations_history,
                            transcript=transcript,
                            steps_count=round_i + 1,
                            reviewer_sys=reviewer_sys,
                            budget=budget,
                            reason="plan_parse_error",
                        )
                    return self._fail(
                        plan.error or "规划解析失败",
                        session_id,
                        trace_id,
                        round_i + 1,
                        transcript,
                    )
                return plan.error or "规划解析失败"

            if plan.decision == "final":
                answer = plan.final_answer or ""
                transcript.append({**round_log, "final_answer": answer})
                self.memory.append(
                    session_id,
                    MemoryRecord(
                        role="assistant",
                        content=answer,
                        meta={"kind": "final_answer"},
                    ),
                )
                metrics.incr("plan_execute_success_total")
                return self._ok(answer, session_id, trace_id, round_i + 1, transcript)

            bad = validate_plan_tools(plan, known)
            if bad:
                metrics.incr("plan_invalid_tool_total")
                reason_s = f"计划含未知工具: {', '.join(bad)}"
                transcript.append({**round_log, "error": reason_s})
                if round_i >= self.max_replans:
                    if observations_history:
                        return await self._force_finalize_review(
                            session_id=session_id,
                            trace_id=trace_id,
                            user_input=user_input,
                            observations_history=observations_history,
                            transcript=transcript,
                            steps_count=round_i + 1,
                            reviewer_sys=reviewer_sys,
                            budget=budget,
                            reason="invalid_tool",
                        )
                    return self._fail(
                        reason_s, session_id, trace_id, round_i + 1, transcript
                    )
                return reason_s

            # P1：执行前裁掉超额 web_search，避免一轮计划塞爆搜索配额
            dropped = self._trim_plan_web_search(plan, budget)
            if dropped:
                round_log["web_search_trimmed"] = dropped
                logger.info(
                    "PE 裁剪 web_search dropped=%s used=%s max=%s",
                    dropped,
                    budget.web_search_calls,
                    self.budget_cfg.web_search_max,
                )
            # 裁完没有可执行步：有观察则收口，否则当作需要重规划的原因
            if not plan.steps:
                transcript.append({**round_log, "error": "web_search_quota_empty_plan"})
                if observations_history:
                    return await self._force_finalize_review(
                        session_id=session_id,
                        trace_id=trace_id,
                        user_input=user_input,
                        observations_history=observations_history,
                        transcript=transcript,
                        steps_count=round_i + 1,
                        reviewer_sys=reviewer_sys,
                        budget=budget,
                        reason="web_search_max",
                    )
                return "web_search 配额已用尽且无可用观察"

            round_log["steps"] = plan_to_tool_calls(plan)
            transcript.append(round_log)
            metrics.incr("plan_execute_rounds_total")

            batch = await executor.run_plan(plan)
            if batch.needs_input and batch.gaps:
                if batch.observation_text and batch.observation_text not in observations_history:
                    observations_history.append(batch.observation_text)
                return emit_needs_input(
                    session_id=session_id,
                    trace_id=trace_id,
                    mode="plan_execute",
                    gaps=batch.gaps,
                    user_input=user_input,
                    payload={
                        "plan": {
                            "thought": plan.thought,
                            "decision": plan.decision,
                            "steps": plan_to_tool_calls(plan),
                        },
                        "completed": _serialize_completed(batch.completed),
                        "observations_history": observations_history,
                        "round_i": round_i,
                        "replan_reason": replan_reason,
                        "transcript": transcript,
                        "skill_ids": skill_ids,
                        "budget": budget.snapshot(self.budget_cfg),
                    },
                    transcript=transcript,
                    steps=round_i + 1,
                    store=self.pending_store,
                )

            n_ws = sum(1 for r in batch.results if r.tool == "web_search")
            if n_ws:
                budget.add_web_search(n_ws)

            obs = batch.observation_text
            observations_history.append(obs)
            # 本轮工具结果只进 observations_history / transcript，不写 memory observation
            transcript.append(
                {
                    "round": round_i,
                    "phase": "execute",
                    "any_failed": batch.any_failed,
                    "budget": budget.snapshot(self.budget_cfg),
                    "results": [
                        {
                            "id": r.call_id,
                            "tool": r.tool,
                            "ok": r.ok,
                            "content": r.content,
                            "exec_mode": r.exec_mode,
                        }
                        for r in batch.results
                    ],
                }
            )

            return await self._gate_and_review(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                plan=plan,
                batch=batch,
                observations_history=observations_history,
                transcript=transcript,
                round_i=round_i,
                steps_count=round_i + 1,
                reviewer_sys=reviewer_sys,
                budget=budget,
            )

    async def _gate_and_review(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        plan: Plan,
        batch: BatchExecResult,
        observations_history: List[str],
        transcript: List[Dict[str, Any]],
        round_i: int,
        steps_count: int,
        reviewer_sys: str,
        budget: RunBudgetState,
    ) -> Union[AgentRunResult, str]:
        """执行后闸门：先代码判计划完成度，再（仅 complete）做质量评审。

        方案 B：
        - 校验对象是「本轮 Planner 的 plan.steps」vs 执行结果，与 skill 无关；
        - 未全部成功 → 禁止 final，返回 replan_reason（str）；
        - 全部成功 → 才调用 Reviewer 做「素材够不够」的质量判断。

        返回 AgentRunResult（结束）或 str（交给上层重规划）。
        """
        metrics = get_metrics()
        # 步骤 1：对照计划与结果（不看工具白名单）
        status = plan_execution_status(plan, batch.results)
        transcript.append(
            {
                "round": round_i,
                "phase": "plan_completion",
                "status": status.status,
                "ok_ids": status.ok_ids,
                "failed_ids": status.failed_ids,
                "pending_ids": status.pending_ids,
                "allows_quality_final": status.allows_quality_final,
            }
        )
        logger.info(
            "plan_completion status=%s ok=%s failed=%s pending=%s",
            status.status,
            ",".join(status.ok_ids) or "-",
            ",".join(status.failed_ids) or "-",
            ",".join(status.pending_ids) or "-",
        )

        # 步骤 2：预算 / 轮次硬闸 → 强制综合（兜底，避免无限 replan）
        force, force_reason = self._budget_should_force(budget)
        if force or round_i >= self.max_replans:
            return await self._force_finalize_review(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                observations_history=observations_history,
                transcript=transcript,
                steps_count=steps_count,
                reviewer_sys=reviewer_sys,
                budget=budget,
                reason=force_reason or "max_replans",
            )

        # 步骤 3：计划未完成或有失败 → 代码直接 replan，不让 Reviewer 提前 final
        if not status.allows_quality_final:
            reason = status.replan_reason()
            rev_log = {
                "round": round_i,
                "phase": "review",
                "decision": "replan",
                "parse_ok": True,
                "gate": status.status,
                "replan_reason": reason,
                "budget": budget.snapshot(self.budget_cfg),
            }
            transcript.append(rev_log)
            metrics.incr("plan_replan_total")
            metrics.incr(
                "plan_completion_block_final_total", status=status.status
            )
            logger.info(
                "完成度闸禁止 final round=%s gate=%s", round_i, status.status
            )
            return reason

        # 步骤 4：计划全部成功 → 质量评审（允许 final / replan）
        obs = batch.observation_text
        review_messages = self._reviewer_messages(
            reviewer_sys,
            user_input,
            observations_history,
            plan=plan,
            execution_status=status,
        )
        rev_model = self.router.get(
            ModelRole.STRONG if batch.any_failed else ModelRole.FAST,
            route_reason="review",
        )
        try:
            rev_out = await self._acall_llm(
                rev_model,
                review_messages,
                role=ModelRole.STRONG if batch.any_failed else ModelRole.FAST,
                route_reason="review",
            )
            budget.add_llm_usage(rev_out.prompt_tokens, rev_out.completion_tokens)
        except Exception as exc:  # noqa: BLE001
            # 计划已跑完且工具都成功时，评审挂了仍可降级用 Observation
            logger.warning("质量评审模型失败，降级输出 Observation: %s", exc)
            return self._ok(
                f"根据工具结果：\n{obs}",
                session_id,
                trace_id,
                steps_count,
                transcript,
            )

        review = parse_review(rev_out.content)
        rev_log = {
            "round": round_i,
            "phase": "review",
            "raw": rev_out.content,
            "decision": review.decision,
            "parse_ok": review.parse_ok,
            "gate": status.status,
            "budget": budget.snapshot(self.budget_cfg),
        }
        self.memory.append(
            session_id,
            MemoryRecord(
                role="assistant",
                content=rev_out.content,
                meta={"kind": "review", "round": round_i},
            ),
        )
        if review.decision == "final" and review.final_answer:
            rev_log["final_answer"] = review.final_answer
            transcript.append(rev_log)
            self.memory.append(
                session_id,
                MemoryRecord(
                    role="assistant",
                    content=review.final_answer,
                    meta={"kind": "final_answer"},
                ),
            )
            metrics.incr("plan_execute_success_total")
            return self._ok(
                review.final_answer,
                session_id,
                trace_id,
                steps_count,
                transcript,
            )

        # 质量不够 → replan；若此时预算硬触顶则收口
        force2, reason2 = self._budget_should_force(budget)
        if force2:
            transcript.append({**rev_log, "replan_blocked": reason2})
            return await self._force_finalize_review(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                observations_history=observations_history,
                transcript=transcript,
                steps_count=steps_count,
                reviewer_sys=reviewer_sys,
                budget=budget,
                reason=reason2,
            )

        metrics.incr("plan_replan_total")
        next_reason = (
            review.replan_reason
            or ("工具执行存在失败" if batch.any_failed else "评审认为结果不合适")
        )
        rev_log["replan_reason"] = next_reason
        transcript.append(rev_log)
        logger.info("触发重规划 round=%s reason=%s", round_i, next_reason)
        return next_reason

    def _planner_messages(
        self,
        system: str,
        session_id: str,
        user_input: str,
        observations: List[str],
        replan_reason: str,
        *,
        soft_budget_hint: str = "",
    ) -> List[ChatMessage]:
        parts = [f"## 用户问题\n{user_input}"]
        if observations:
            parts.append("## 已有 Observation\n" + "\n---\n".join(observations))
        if replan_reason:
            parts.append(f"## 重规划原因\n{replan_reason}")
        # 软预算提示：插在输出要求前，提高遵从率
        if soft_budget_hint:
            parts.append(soft_budget_hint)
        if isinstance(self.memory, SessionMemoryStore):
            mem_text = self.memory.format_for_prompt(
                session_id, exclude_last_user=True
            )
        else:
            mem_text = ""
        if mem_text.strip():
            parts.append("## 会话记忆（近3轮对话骨架 + 更早摘要）\n" + mem_text)
        parts.append("请输出规划 JSON。")
        return [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content="\n\n".join(parts)),
        ]

    def _reviewer_messages(
        self,
        system: str,
        user_input: str,
        observations: List[str],
        *,
        force_final: bool = False,
        plan: Optional[Plan] = None,
        execution_status: Optional[PlanExecutionStatus] = None,
    ) -> List[ChatMessage]:
        parts = [
            f"## 用户问题\n{user_input}",
            "## Observation\n" + ("\n---\n".join(observations) if observations else "(无)"),
        ]
        # 把「已执行计划」给 Reviewer 对照，避免它只凭检索摘要就收口却不知道计划范围
        if plan is not None:
            gate = execution_status.status if execution_status else "unknown"
            parts.append(
                "## 本轮已执行计划（代码完成度="
                + gate
                + "）\n"
                + format_plan_for_review(plan)
            )
        # force_final=True：系统收口，禁止再要求 replan
        if force_final:
            parts.append(_FORCE_FINAL_REVIEW_HINT)
        parts.append("请输出评审 JSON。")
        return [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content="\n\n".join(parts)),
        ]

    async def _acall_llm(
        self,
        model: ChatModel,
        messages: List[ChatMessage],
        *,
        role: ModelRole,
        route_reason: str,
        tools: Optional[List[dict]] = None,
    ):
        dep = f"model:{model.provider}:{model.model_id}"

        async def _once():
            with get_tracer().span(
                "llm.call",
                model=model.model_id,
                role=role.value,
                route_reason=route_reason,
            ):
                return await asyncio.to_thread(
                    model.complete,
                    messages,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                )

        return await call_with_retry_async(dep, _once, self.llm_retry)

    def _tree(self) -> Optional[Dict[str, Any]]:
        root = get_tracer().root
        return root.to_dict() if root else None

    def _ok(
        self,
        answer: str,
        session_id: str,
        trace_id: str,
        steps: int,
        transcript: List[Dict[str, Any]],
    ) -> AgentRunResult:
        return AgentRunResult(
            answer=answer,
            session_id=session_id,
            trace_id=trace_id,
            steps=steps,
            status="ok",
            user_input=getattr(self, "_run_user_input", "") or "",
            transcript=transcript,
            trace_tree=self._tree(),
        )

    def _fail(
        self,
        err: str,
        session_id: str,
        trace_id: str,
        steps: int,
        transcript: List[Dict[str, Any]],
    ) -> AgentRunResult:
        self.memory.append(session_id, MemoryRecord(role="assistant", content=err))
        return AgentRunResult(
            answer=err,
            session_id=session_id,
            trace_id=trace_id,
            steps=steps,
            status="error",
            error=err,
            user_input=getattr(self, "_run_user_input", "") or "",
            transcript=transcript,
            trace_tree=self._tree(),
        )
