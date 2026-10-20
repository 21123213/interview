"""ReAct 主循环（原生 function calling）。

流程：LLM（tools）→ tool_calls → 执行 → tool 消息 → … → 最终 content。
缺参时 status=needs_input，立刻返回；由外壳收集答案后 aresume。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from agent.memory.base import MemoryRecord, MemoryStore
from agent.memory.windowed import SessionMemoryStore
from agent.models.base import ChatMessage, ChatModel
from agent.models.router import ModelRole, ModelRouter
from agent.observability.context import get_trace_id
from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer
from agent.prompts.react import build_react_system_prompt
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
from agent.runtime.result import AgentRunResult
from agent.runtime.tool_calls import (
    ToolCallSpec,
    openai_tool_calls_payload,
    specs_from_model_result,
)
from agent.runtime.tool_executor import BatchExecResult, ToolExecutor
from agent.tools.registry import ToolRegistry

# 强制收口时注入的用户提示（禁止再搜，基于已有 observation 作答）
_FORCE_FINAL_HINT = (
    "【系统收口】请基于以上已有工具结果，直接给出完整中文回答。"
    "不要再调用任何工具；不确定的信息请标注「以现场/官网为准」。"
)
_SOFT_BUDGET_HINT = (
    "【预算提示】本轮上下文消耗已较高，请停止新的网页搜索，"
    "基于已有信息整理中文答案；缺资料处标注「以现场/官网为准」。"
)

logger = logging.getLogger("agent.runtime.loop")

__all__ = ["AgentRunResult", "ReactAgentLoop"]


def _serialize_messages(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in messages:
        item: Dict[str, Any] = {"role": m.role, "content": m.content or ""}
        if m.name:
            item["name"] = m.name
        if m.tool_call_id:
            item["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            item["tool_calls"] = m.tool_calls
        out.append(item)
    return out


def _deserialize_messages(raw: List[Dict[str, Any]]) -> List[ChatMessage]:
    messages: List[ChatMessage] = []
    for item in raw:
        messages.append(
            ChatMessage(
                role=str(item.get("role") or "user"),
                content=str(item.get("content") or ""),
                name=item.get("name"),
                tool_call_id=item.get("tool_call_id"),
                tool_calls=item.get("tool_calls"),
            )
        )
    return messages


class ReactAgentLoop:
    """ReAct 运行时（原生 tools API）。"""

    def __init__(
        self,
        *,
        router: ModelRouter,
        tools: ToolRegistry,
        memory: MemoryStore,
        max_steps: int = 12,
        max_parallel_tools: int = 5,
        tool_retry: Optional[RetryPolicy] = None,
        llm_retry: Optional[RetryPolicy] = None,
        pending_store: Optional[PendingStore] = None,
    ) -> None:
        self.router = router
        self.tools = tools
        self.memory = memory
        self.pending_store = pending_store or PendingStore()
        self.max_steps = max_steps
        self.tool_retry = tool_retry or RetryPolicy(
            max_attempts=3,
            backoff=BackoffPolicy(base_ms=200, factor=2.0, max_ms=4000),
        )
        self.llm_retry = llm_retry or RetryPolicy(
            max_attempts=2,
            backoff=BackoffPolicy(base_ms=300, factor=2.0, max_ms=3000),
        )
        self.executor = ToolExecutor(
            tools,
            retry=self.tool_retry,
            max_parallel=max_parallel_tools,
        )
        # P2：单轮 token / web_search 预算（环境变量可调，见 budget.py）
        self.budget_cfg: RunBudgetConfig = load_run_budget_config()

    def run(self, user_input: str, session_id: str) -> AgentRunResult:
        return asyncio.run(self.arun(user_input, session_id))

    def _make_executor(self, tools: ToolRegistry) -> ToolExecutor:
        return ToolExecutor(
            tools,
            retry=self.tool_retry,
            max_parallel=self.executor.max_parallel,
        )

    async def arun(
        self,
        user_input: str,
        session_id: str,
        *,
        tools: Optional[ToolRegistry] = None,
        skill_ids: Optional[List[str]] = None,
    ) -> AgentRunResult:
        tracer = get_tracer()
        metrics = get_metrics()
        trace_id = get_trace_id()
        transcript: List[Dict[str, Any]] = []
        tools = tools or self.tools
        skill_ids = list(skill_ids or [])
        executor = self._make_executor(tools)
        tool_defs = tools.openai_tool_definitions()

        transcript.append(
            {
                "phase": "tool_registry",
                "skills": skill_ids,
                "tools": tools.names(),
            }
        )
        logger.info(
            "react registry session=%s skills=%s tools=%s",
            session_id,
            skill_ids or ["(none)"],
            tools.names(),
        )

        self.memory.append(
            session_id,
            MemoryRecord(role="user", content=user_input),
        )
        if isinstance(self.memory, SessionMemoryStore):
            await self.memory.compact(session_id)

        # 用粘滞后的 skill_ids 注入 SKILL.md，不能只看本轮 user_input 正则
        system_prompt = build_react_system_prompt(user_input, skill_ids=skill_ids)
        messages: List[ChatMessage] = self._build_initial_messages(
            system_prompt=system_prompt,
            session_id=session_id,
            current_user=user_input,
        )

        return await self._arun_loop(
            session_id=session_id,
            trace_id=trace_id,
            user_input=user_input,
            messages=messages,
            transcript=transcript,
            tool_defs=tool_defs,
            tools=tools,
            executor=executor,
            skill_ids=skill_ids,
            start_step=1,
            pending_calls=None,
            metrics=metrics,
            tracer=tracer,
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
        calls: List[ToolCallSpec] = []
        for item in payload.get("calls") or []:
            cid = str(item.get("call_id") or item.get("id") or "")
            args = merge_answers_into_args(
                dict(item.get("arguments") or item.get("input") or {}),
                pending.questions,
                parsed,
                cid,
            )
            calls.append(
                ToolCallSpec(
                    name=str(item.get("tool") or item.get("name") or ""),
                    arguments=args,
                    call_id=cid,
                )
            )
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
        return await self._arun_loop(
            session_id=session_id,
            trace_id=get_trace_id(),
            user_input=pending.user_input,
            messages=_deserialize_messages(list(payload.get("messages") or [])),
            transcript=list(payload.get("transcript") or []),
            tool_defs=tools.openai_tool_definitions(),
            tools=tools,
            executor=executor,
            skill_ids=skill_ids,
            start_step=int(payload.get("step") or 1),
            pending_calls=calls,
            metrics=get_metrics(),
            tracer=get_tracer(),
        )

    def _should_force_finalize(
        self,
        *,
        step: int,
        budget: RunBudgetState,
    ) -> tuple[bool, str]:
        """是否禁止工具并强制综合答案。返回 (强制?, 原因码)。"""
        cfg = self.budget_cfg
        # 最后一步不再给工具轮次，避免搜到天花板仍无答案
        if step >= self.max_steps:
            return True, "max_steps"
        if budget.prompt_tokens >= cfg.hard_tokens:
            return True, "token_hard"
        if budget.web_search_calls >= cfg.web_search_max:
            return True, "web_search_max"
        return False, ""

    async def _force_finalize(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        messages: List[ChatMessage],
        transcript: List[Dict[str, Any]],
        step: int,
        metrics,
        reason: str,
        budget: RunBudgetState,
    ) -> AgentRunResult:
        """P0 硬收口：tool_choice=none，基于已有 observation 生成最终答案。

        不再返回罐头「未能给出完整结论」，避免用户白跑一轮搜索。
        """
        messages.append(ChatMessage(role="user", content=_FORCE_FINAL_HINT))
        model, role, route_reason = self.router.resolve_for_react(
            step_index=step, force_strong=True
        )
        route_reason = f"force_finalize:{reason}"
        try:
            llm_out = await self._acall_llm(
                model,
                messages,
                tools=[],
                tool_choice="none",
                role=role,
                route_reason=route_reason,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("强制收口 LLM 失败: %s", exc)
            fallback = (
                "检索已达上限，未能自动整理完整结论。"
                "请稍后重试，或把问题拆得更具体一些。"
            )
            transcript.append(
                {
                    "step": step,
                    "phase": "force_finalize",
                    "reason": reason,
                    "error": str(exc),
                    "budget": {
                        "prompt_tokens": budget.prompt_tokens,
                        "completion_tokens": budget.completion_tokens,
                        "web_search_calls": budget.web_search_calls,
                    },
                }
            )
            self.memory.append(
                session_id,
                MemoryRecord(
                    role="assistant", content=fallback, meta={"kind": "max_steps"}
                ),
            )
            metrics.incr("react_max_steps_total")
            return self._result(
                answer=fallback,
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                steps=step,
                status="max_steps",
                error=str(exc),
                transcript=transcript,
            )

        budget.add_llm_usage(llm_out.prompt_tokens, llm_out.completion_tokens)
        answer = (llm_out.content or "").strip()
        step_log: Dict[str, Any] = {
            "step": step,
            "phase": "force_finalize",
            "reason": reason,
            "model": llm_out.model,
            "role": role.value,
            "route_reason": route_reason,
            "content": llm_out.content,
            "tool_calls": [],
            "prompt_tokens": llm_out.prompt_tokens,
            "completion_tokens": llm_out.completion_tokens,
            "latency_ms": round(llm_out.latency_ms, 2),
            "budget": {
                "prompt_tokens": budget.prompt_tokens,
                "completion_tokens": budget.completion_tokens,
                "web_search_calls": budget.web_search_calls,
                "token_budget": self.budget_cfg.token_budget,
                "web_search_max": self.budget_cfg.web_search_max,
            },
        }
        if not answer:
            answer = (
                "已收集到部分资料，但模型未能整理出完整回答。"
                "请换种问法或缩小范围后再试。"
            )
            step_log["final_answer"] = answer
            transcript.append(step_log)
            self.memory.append(
                session_id,
                MemoryRecord(
                    role="assistant", content=answer, meta={"kind": "max_steps"}
                ),
            )
            metrics.incr("react_max_steps_total")
            return self._result(
                answer=answer,
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                steps=step,
                status="max_steps",
                transcript=transcript,
            )

        step_log["final_answer"] = answer
        transcript.append(step_log)
        self.memory.append(
            session_id,
            MemoryRecord(
                role="assistant",
                content=answer,
                meta={"kind": "final_answer", "step": step, "force_reason": reason},
            ),
        )
        # 触顶收口仍算成功给出答案；另记计数便于观测
        metrics.incr("react_force_finalize_total", reason=reason)
        metrics.incr("react_success_total")
        return self._result(
            answer=answer,
            session_id=session_id,
            trace_id=trace_id,
            user_input=user_input,
            steps=step,
            status="ok",
            transcript=transcript,
        )

    def _split_web_search_quota(
        self,
        calls: List[ToolCallSpec],
        budget: RunBudgetState,
    ) -> tuple[List[ToolCallSpec], List[ToolCallSpec]]:
        """按单轮 web_search 上限拆分：可执行 vs 超限需 stub。"""
        remaining = max(0, self.budget_cfg.web_search_max - budget.web_search_calls)
        allowed: List[ToolCallSpec] = []
        blocked: List[ToolCallSpec] = []
        used = 0
        for c in calls:
            if c.name == "web_search":
                if used < remaining:
                    allowed.append(c)
                    used += 1
                else:
                    blocked.append(c)
            else:
                allowed.append(c)
        return allowed, blocked

    async def _arun_loop(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        messages: List[ChatMessage],
        transcript: List[Dict[str, Any]],
        tool_defs: List[dict],
        tools: ToolRegistry,
        executor: ToolExecutor,
        skill_ids: List[str],
        start_step: int,
        pending_calls: Optional[List[ToolCallSpec]],
        metrics,
        tracer,
    ) -> AgentRunResult:
        # 本轮累计预算状态（跨 step；不跨用户提问）
        budget = RunBudgetState()
        with tracer.span(
            "react.run",
            session_id=session_id,
            user_input=user_input,
            skills=",".join(skill_ids) or "(none)",
            tools=",".join(tools.names()),
        ):
            if pending_calls:
                step = max(1, start_step)
                # resume 补参后的工具批也计入 web_search 配额
                allowed, blocked = self._split_web_search_quota(pending_calls, budget)
                if allowed or blocked:
                    ni = await self._execute_calls_or_pause(
                        session_id=session_id,
                        trace_id=trace_id,
                        user_input=user_input,
                        messages=messages,
                        transcript=transcript,
                        step=step,
                        calls=allowed,
                        llm_content="",
                        tool_calls_payload=[],
                        executor=executor,
                        skill_ids=skill_ids,
                        budget=budget,
                        blocked_calls=blocked,
                    )
                    if ni is not None:
                        return ni
                start_step = step + 1

            for step in range(start_step, self.max_steps + 1):
                with tracer.span("react.step", step=step):
                    force, force_reason = self._should_force_finalize(
                        step=step, budget=budget
                    )
                    if force:
                        return await self._force_finalize(
                            session_id=session_id,
                            trace_id=trace_id,
                            user_input=user_input,
                            messages=messages,
                            transcript=transcript,
                            step=step,
                            metrics=metrics,
                            reason=force_reason,
                            budget=budget,
                        )

                    # P2 软预算：提示停搜，但仍允许本轮工具
                    if (
                        not budget.soft_nudged
                        and budget.prompt_tokens >= self.budget_cfg.soft_tokens
                    ):
                        messages.append(
                            ChatMessage(role="user", content=_SOFT_BUDGET_HINT)
                        )
                        budget.soft_nudged = True
                        logger.info(
                            "软预算触发 session=%s prompt_tokens=%s soft=%s",
                            session_id,
                            budget.prompt_tokens,
                            self.budget_cfg.soft_tokens,
                        )

                    model, role, route_reason = self.router.resolve_for_react(
                        step_index=step
                    )
                    try:
                        llm_out = await self._acall_llm(
                            model,
                            messages,
                            tools=tool_defs,
                            tool_choice="auto",
                            role=role,
                            route_reason=route_reason,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.error("LLM 调用失败，尝试强模型升级: %s", exc)
                        try:
                            strong = self.router.get(
                                ModelRole.STRONG, route_reason="llm_fail_upgrade"
                            )
                            llm_out = await self._acall_llm(
                                strong,
                                messages,
                                tools=tool_defs,
                                tool_choice="auto",
                                role=ModelRole.STRONG,
                                route_reason="llm_fail_upgrade",
                            )
                        except Exception as exc2:  # noqa: BLE001
                            err = f"模型调用失败: {exc2}"
                            self.memory.append(
                                session_id,
                                MemoryRecord(role="assistant", content=err),
                            )
                            return self._result(
                                answer=err,
                                session_id=session_id,
                                trace_id=trace_id,
                                user_input=user_input,
                                steps=step,
                                status="error",
                                error=str(exc2),
                                transcript=transcript,
                            )

                    budget.add_llm_usage(
                        llm_out.prompt_tokens, llm_out.completion_tokens
                    )
                    calls = specs_from_model_result(llm_out)
                    step_log: Dict[str, Any] = {
                        "step": step,
                        "model": llm_out.model,
                        "role": role.value,
                        "route_reason": route_reason,
                        "content": llm_out.content,
                        "tool_calls": [
                            {
                                "id": c.call_id,
                                "tool": c.name,
                                "input": c.arguments,
                            }
                            for c in calls
                        ],
                        "prompt_tokens": llm_out.prompt_tokens,
                        "completion_tokens": llm_out.completion_tokens,
                        "latency_ms": round(llm_out.latency_ms, 2),
                        "budget": {
                            "prompt_tokens": budget.prompt_tokens,
                            "web_search_calls": budget.web_search_calls,
                        },
                    }
                    logger.info(
                        "ReAct step=%s model=%s tools=%s prompt_tok=%s web_search=%s content=%s",
                        step,
                        llm_out.model,
                        len(calls),
                        budget.prompt_tokens,
                        budget.web_search_calls,
                        (llm_out.content or "")[:120],
                    )

                    if not calls:
                        answer = (llm_out.content or "").strip()
                        if not answer:
                            hint = "请调用工具完成任务，或直接给出中文回答。"
                            messages.append(ChatMessage(role="user", content=hint))
                            step_log["hint"] = hint
                            transcript.append(step_log)
                            metrics.incr("react_empty_output_total")
                            continue

                        step_log["final_answer"] = answer
                        transcript.append(step_log)
                        self.memory.append(
                            session_id,
                            MemoryRecord(
                                role="assistant",
                                content=answer,
                                meta={"kind": "final_answer", "step": step},
                            ),
                        )
                        metrics.incr("react_success_total")
                        return self._result(
                            answer=answer,
                            session_id=session_id,
                            trace_id=trace_id,
                            user_input=user_input,
                            steps=step,
                            status="ok",
                            transcript=transcript,
                        )

                    if len(calls) > 1:
                        metrics.incr(
                            "react_multi_tool_total",
                            count=str(len(calls)),
                        )

                    # P1：超限的 web_search 不执行，在 tool 结果里写 stub（ID 配对）
                    allowed, blocked = self._split_web_search_quota(calls, budget)
                    if blocked:
                        step_log["web_search_blocked"] = len(blocked)
                        logger.info(
                            "web_search 配额截断 blocked=%s used=%s max=%s",
                            len(blocked),
                            budget.web_search_calls,
                            self.budget_cfg.web_search_max,
                        )

                    if not allowed and not blocked:
                        transcript.append(step_log)
                        return await self._force_finalize(
                            session_id=session_id,
                            trace_id=trace_id,
                            user_input=user_input,
                            messages=messages,
                            transcript=transcript,
                            step=step,
                            metrics=metrics,
                            reason="web_search_max",
                            budget=budget,
                        )

                    # assistant 消息带完整 tool_calls；只执行 allowed，blocked 用 stub 配对
                    tc_payload = openai_tool_calls_payload(llm_out.tool_calls)
                    ni = await self._execute_calls_or_pause(
                        session_id=session_id,
                        trace_id=trace_id,
                        user_input=user_input,
                        messages=messages,
                        transcript=transcript,
                        step=step,
                        calls=allowed,
                        llm_content=llm_out.content or "",
                        tool_calls_payload=tc_payload,
                        step_log=step_log,
                        llm_model=llm_out.model,
                        executor=executor,
                        skill_ids=skill_ids,
                        budget=budget,
                        blocked_calls=blocked,
                    )
                    if ni is not None:
                        return ni

                    # 本批全被配额挡住 → 立刻收口
                    if not allowed and blocked:
                        return await self._force_finalize(
                            session_id=session_id,
                            trace_id=trace_id,
                            user_input=user_input,
                            messages=messages,
                            transcript=transcript,
                            step=step,
                            metrics=metrics,
                            reason="web_search_max",
                            budget=budget,
                        )

                    # 执行后若已触顶，下一步循环开头会 force_finalize
                    force_after, reason_after = self._should_force_finalize(
                        step=step + 1, budget=budget
                    )
                    if force_after and reason_after != "max_steps":
                        return await self._force_finalize(
                            session_id=session_id,
                            trace_id=trace_id,
                            user_input=user_input,
                            messages=messages,
                            transcript=transcript,
                            step=step,
                            metrics=metrics,
                            reason=reason_after,
                            budget=budget,
                        )

            # 正常 for 结束仍无最终答案 → 强制综合（不再返回罐头文案）
            return await self._force_finalize(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                messages=messages,
                transcript=transcript,
                step=self.max_steps,
                metrics=metrics,
                reason="max_steps",
                budget=budget,
            )

    def _append_quota_stubs(
        self,
        messages: List[ChatMessage],
        blocked: List[ToolCallSpec],
        budget: RunBudgetState,
    ) -> None:
        """为超限 web_search 补 tool 消息，满足 API tool_call_id 配对。"""
        stub = (
            '{"ok": false, "error": "本轮 web_search 次数已达上限，请基于已有结果作答", '
            f'"code": "web_search_quota", "used": {budget.web_search_calls}, '
            f'"max": {self.budget_cfg.web_search_max}}}'
        )
        for c in blocked:
            messages.append(
                ChatMessage(
                    role="tool",
                    content=stub,
                    name=c.name or "web_search",
                    tool_call_id=c.call_id,
                )
            )

    async def _execute_calls_or_pause(
        self,
        *,
        session_id: str,
        trace_id: str,
        user_input: str,
        messages: List[ChatMessage],
        transcript: List[Dict[str, Any]],
        step: int,
        calls: List[ToolCallSpec],
        llm_content: str,
        tool_calls_payload: List[Dict[str, Any]],
        executor: ToolExecutor,
        skill_ids: List[str],
        step_log: Optional[Dict[str, Any]] = None,
        llm_model: str = "",
        budget: Optional[RunBudgetState] = None,
        blocked_calls: Optional[List[ToolCallSpec]] = None,
    ) -> Optional[AgentRunResult]:
        blocked_calls = list(blocked_calls or [])
        # 无实际可执行调用时仍可能只有 blocked stubs
        if calls:
            batch = await executor.run_calls(calls)
        else:
            # 仅有配额 stub、无可执行工具时的空批次
            batch = BatchExecResult()

        if batch.needs_input and batch.gaps:
            # assistant 已决定调用，但缺参：先不写 tool 结果，挂起等用户
            if tool_calls_payload:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=llm_content,
                        tool_calls=tool_calls_payload,
                    )
                )
            if step_log is not None:
                step_log["needs_input"] = True
                transcript.append(step_log)
            return emit_needs_input(
                session_id=session_id,
                trace_id=trace_id,
                mode="react",
                gaps=batch.gaps,
                user_input=user_input,
                payload={
                    "messages": _serialize_messages(messages),
                    "calls": [
                        {
                            "call_id": c.call_id,
                            "tool": c.name,
                            "arguments": c.arguments,
                        }
                        for c in calls
                    ],
                    "step": step,
                    "transcript": transcript,
                    "skill_ids": skill_ids,
                },
                transcript=transcript,
                steps=step,
                store=self.pending_store,
            )

        if tool_calls_payload and (
            not messages
            or messages[-1].role != "assistant"
            or not messages[-1].tool_calls
        ):
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=llm_content,
                    tool_calls=tool_calls_payload,
                )
            )
            self.memory.append(
                session_id,
                MemoryRecord(
                    role="assistant",
                    content=llm_content,
                    meta={
                        "step": step,
                        "model": llm_model,
                        "tool_calls": [
                            {"id": c.call_id, "tool": c.name, "input": c.arguments}
                            for c in calls
                        ],
                    },
                ),
            )

        self._apply_batch(
            session_id=session_id,
            messages=messages,
            transcript=transcript,
            step=step,
            calls=calls,
            batch=batch,
            step_log=step_log,
        )
        # 累计本批实际执行的 web_search 次数（配额）
        if budget is not None:
            n_ws = sum(1 for c in calls if c.name == "web_search")
            if n_ws:
                budget.add_web_search(n_ws)
        # 超限调用的 stub 必须接在真实 tool 结果之后，保证 tool_call_id 齐全
        if blocked_calls and budget is not None:
            self._append_quota_stubs(messages, blocked_calls, budget)
            if step_log is not None and isinstance(step_log.get("tool_results"), list):
                stub_content = (
                    '{"ok": false, "error": "本轮 web_search 次数已达上限", '
                    '"code": "web_search_quota"}'
                )
                for c in blocked_calls:
                    step_log["tool_results"].append(
                        {
                            "id": c.call_id,
                            "tool": c.name,
                            "ok": False,
                            "exec_mode": "local",
                            "content": stub_content,
                        }
                    )
        return None

    def _apply_batch(
        self,
        *,
        session_id: str,
        messages: List[ChatMessage],
        transcript: List[Dict[str, Any]],
        step: int,
        calls: List[ToolCallSpec],
        batch: BatchExecResult,
        step_log: Optional[Dict[str, Any]],
    ) -> None:
        log = step_log if step_log is not None else {"step": step}
        log["any_failed"] = batch.any_failed
        log["tool_results"] = [
            {
                "id": r.call_id,
                "tool": r.tool,
                "ok": r.ok,
                "exec_mode": r.exec_mode,
                "content": r.content,
            }
            for r in batch.results
        ]
        transcript.append(log)

        self.memory.append(
            session_id,
            MemoryRecord(
                role="action",
                content=json.dumps(
                    {
                        "tool_calls": [
                            {"id": c.call_id, "tool": c.name, "input": c.arguments}
                            for c in calls
                        ]
                    },
                    ensure_ascii=False,
                ),
                meta={"step": step, "count": len(calls)},
            ),
        )
        for r in batch.results:
            messages.append(
                ChatMessage(
                    role="tool",
                    content=r.content,
                    name=r.tool,
                    tool_call_id=r.call_id,
                )
            )
            self.memory.append(
                session_id,
                MemoryRecord(
                    role="tool",
                    content=r.content,
                    meta={
                        "step": step,
                        "tool": r.tool,
                        "tool_call_id": r.call_id,
                        "ok": r.ok,
                    },
                ),
            )

    def _result(self, **kwargs: Any) -> AgentRunResult:
        root = get_tracer().root
        kwargs.setdefault("trace_tree", root.to_dict() if root else None)
        return AgentRunResult(**kwargs)

    def _build_initial_messages(
        self,
        *,
        system_prompt: str,
        session_id: str,
        current_user: str,
    ) -> List[ChatMessage]:
        history_text = self._history_for_prompt(session_id, exclude_last_user=True)
        parts: List[str] = []
        if history_text:
            parts.append("## 会话记忆（近3轮对话骨架 + 更早摘要）\n" + history_text)
        parts.append("## 当前用户问题\n" + current_user)
        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content="\n\n".join(parts)),
        ]

    def _history_for_prompt(self, session_id: str, exclude_last_user: bool) -> str:
        if isinstance(self.memory, SessionMemoryStore):
            return self.memory.format_for_prompt(
                session_id, exclude_last_user=exclude_last_user
            )
        records = self.memory.get_all(session_id)
        if exclude_last_user and records and records[-1].role == "user":
            records = records[:-1]
        from agent.memory.format import format_skeleton_records

        return format_skeleton_records(records)

    async def _acall_llm(
        self,
        model: ChatModel,
        messages: List[ChatMessage],
        *,
        tools: List[dict],
        role: ModelRole,
        route_reason: str,
        tool_choice: str = "auto",
    ):
        dep = f"model:{model.provider}:{model.model_id}"
        # 收口：不传 tools，模型只能出文本（DashScope 仅在有 tools 时带 tool_choice）
        if tool_choice == "none" or not tools:
            tools_arg: Optional[List[dict]] = None
            choice_arg: Optional[str] = None
        else:
            tools_arg = tools
            choice_arg = tool_choice

        async def _once():
            with get_tracer().span(
                "llm.call",
                model=model.model_id,
                provider=model.provider,
                role=role.value,
                route_reason=route_reason,
                tool_choice=tool_choice,
            ):
                return await asyncio.to_thread(
                    model.complete,
                    messages,
                    tools=tools_arg,
                    tool_choice=choice_arg,
                )

        return await call_with_retry_async(dep, _once, self.llm_retry)
