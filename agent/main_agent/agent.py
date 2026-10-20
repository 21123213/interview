"""主 Agent：组装路由、工具、记忆；按 mode 选择 ReAct 或 Plan-Execute。

默认将 memory / pending / skills 落到 Redis（AGENT_MEMORY_BACKEND=redis），
与 backend 共用 REDIS_*；前端清除会话仍调 memory.clear + pending.clear + skills.clear。
设 AGENT_MEMORY_BACKEND=memory 可回退进程内（单机调试）。
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, AsyncIterator, Literal, Optional

from agent.clients.redis_client import use_redis_memory
from agent.memory.summarizer import LlmSummarizer
from agent.memory.windowed import SessionMemoryStore
from agent.models.router import ModelRouter, get_default_router
from agent.observability.context import (
    TraceContext,
    clear_trace_context,
    new_trace_id,
    set_trace_context,
)
from agent.observability.metrics import get_metrics
from agent.observability.tracer import get_tracer
from agent.runtime.loop import ReactAgentLoop
from agent.runtime.pending import PendingStore
from agent.runtime.plan_execute_loop import PlanExecuteLoop
from agent.runtime.result import AgentRunResult
from agent.runtime.stream import (
    StreamEvent,
    emit_log,
    emit_stream,
    ensure_stream_logging,
    iter_with_task,
    reset_stream_queue,
    set_stream_queue,
)
from agent.skills.loader import merge_session_skills, resolve_skills
from agent.tools.registry import (
    ToolRegistry,
    build_default_registry,
    build_registry_for_skills,
)

logger = logging.getLogger("agent.main_agent")

RunMode = Literal["react", "plan_execute"]


def _build_default_memory(router: ModelRouter) -> SessionMemoryStore:
    """按环境变量选择内存或 Redis 工作记忆。"""
    summarizer = LlmSummarizer(router)
    if use_redis_memory():
        from agent.memory.redis_store import RedisSessionMemoryStore

        logger.info("MainAgent memory backend=redis")
        return RedisSessionMemoryStore(recent_rounds=3, summarizer=summarizer)
    logger.info("MainAgent memory backend=memory")
    return SessionMemoryStore(recent_rounds=3, summarizer=summarizer)


def _build_default_pending() -> PendingStore:
    if use_redis_memory():
        from agent.runtime.pending_redis import RedisPendingStore

        return RedisPendingStore()
    return PendingStore()


class MainAgent:
    """面向业务的主 Agent 门面。"""

    def __init__(
        self,
        *,
        router: Optional[ModelRouter] = None,
        tools: Optional[ToolRegistry] = None,
        memory: Optional[SessionMemoryStore] = None,
        max_steps: int = 8,
        max_replans: int = 2,
        max_parallel_tools: int = 5,
        mode: Optional[RunMode] = None,
        name: str = "main_agent",
    ) -> None:
        self.name = name
        env_mode = (os.getenv("AGENT_RUN_MODE") or "react").strip().lower()
        if mode is None:
            mode = "plan_execute" if env_mode in ("plan_execute", "plan", "pe") else "react"
        self.mode: RunMode = mode
        self.router = router or get_default_router()
        self.tools = tools or build_default_registry()
        self.memory = memory or _build_default_memory(self.router)
        self.pending_store = _build_default_pending()
        self.max_parallel_tools = max_parallel_tools
        self.react_loop = ReactAgentLoop(
            router=self.router,
            tools=self.tools,
            memory=self.memory,
            max_steps=max_steps,
            max_parallel_tools=max_parallel_tools,
            pending_store=self.pending_store,
        )
        self.plan_loop = PlanExecuteLoop(
            router=self.router,
            tools=self.tools,
            memory=self.memory,
            max_replans=max_replans,
            max_parallel_tools=max_parallel_tools,
            pending_store=self.pending_store,
        )
        # 兼容旧属性名
        self.loop = self.react_loop
        # 会话级技能粘滞：默认 Redis；memory 模式用进程 dict
        if use_redis_memory():
            from agent.runtime.skills_redis import RedisSessionSkillsStore

            self._skills_store = RedisSessionSkillsStore()
            self._session_skills: dict[str, list[str]] = {}  # 兼容旧 clear 代码路径
        else:
            self._skills_store = None
            self._session_skills = {}

    def _skills_for_session(self, session_id: str, user_input: str) -> list[str]:
        """本轮正则解析 ∪ 历史粘滞技能，并写回 session。"""
        current = resolve_skills(user_input)
        if self._skills_store is not None:
            previous = self._skills_store.get(session_id)
            merged = merge_session_skills(previous, current)
            self._skills_store.set(session_id, merged)
            return merged
        previous = self._session_skills.get(session_id, [])
        merged = merge_session_skills(previous, current)
        self._session_skills[session_id] = merged
        return merged

    def clear_session_state(self, session_id: str) -> None:
        """清空该会话 memory / pending / skills（前端清除会话入口）。"""
        self.memory.clear(session_id)
        self.pending_store.clear(session_id)
        if self._skills_store is not None:
            self._skills_store.clear(session_id)
        self._session_skills.pop(session_id, None)

    def run(
        self,
        user_input: str,
        *,
        session_id: Optional[str] = None,
        user_id: str = "",
        mode: Optional[RunMode] = None,
    ) -> AgentRunResult:
        return asyncio.run(
            self.arun(
                user_input, session_id=session_id, user_id=user_id, mode=mode
            )
        )

    def resume(
        self,
        answers: Any,
        *,
        session_id: str,
        user_id: str = "",
        resume_token: str = "",
    ) -> AgentRunResult:
        return asyncio.run(
            self.aresume(
                answers,
                session_id=session_id,
                user_id=user_id,
                resume_token=resume_token,
            )
        )

    async def arun(
        self,
        user_input: str,
        *,
        session_id: Optional[str] = None,
        user_id: str = "",
        mode: Optional[RunMode] = None,
    ) -> AgentRunResult:
        """异步入口。mode: react | plan_execute。

        若已有 pending，新输入会清掉旧挂起（重新开跑），除非走 aresume。
        """
        session_id = session_id or uuid.uuid4().hex
        run_mode: RunMode = mode or self.mode
        # 新问题覆盖未完成的补参
        self.pending_store.clear(session_id)
        # P0：会话粘滞 skill，避免「改动线」跟进句丢掉 travel 工具
        skill_ids = self._skills_for_session(session_id, user_input)
        tools = build_registry_for_skills(skill_ids)
        # travel_skill 观测：对齐同一 session_id，便于 JSONL 按会话看成本
        try:
            from travel_skill.shared import observability as travel_obs

            travel_obs.start_session(session_id)
        except Exception:  # noqa: BLE001
            logger.debug("travel_skill obs start_session 跳过", exc_info=True)
        logger.info(
            "请求工具视图 session=%s skills=%s tools=%s",
            session_id,
            skill_ids or ["(none)"],
            tools.names(),
        )
        return await self._run_traced(
            session_id=session_id,
            user_id=user_id,
            run_mode=run_mode,
            coro_factory=lambda: (
                self.plan_loop.arun(
                    user_input,
                    session_id=session_id,
                    tools=tools,
                    skill_ids=skill_ids,
                )
                if run_mode == "plan_execute"
                else self.react_loop.arun(
                    user_input,
                    session_id=session_id,
                    tools=tools,
                    skill_ids=skill_ids,
                )
            ),
            log_input=user_input,
        )

    async def aresume(
        self,
        answers: Any,
        *,
        session_id: str,
        user_id: str = "",
        resume_token: str = "",
    ) -> AgentRunResult:
        """用用户补充继续上次 needs_input（按 session 隔离，不阻塞其它用户）。"""
        pending = self.pending_store.get(session_id)
        if pending is None:
            return AgentRunResult(
                answer="没有待补充的问题，请直接提问。",
                session_id=session_id,
                trace_id=new_trace_id(),
                status="error",
                error="no_pending",
            )
        if resume_token and resume_token != pending.resume_token:
            return AgentRunResult(
                answer="补参令牌已过期或不匹配，请重新提问。",
                session_id=session_id,
                trace_id=new_trace_id(),
                status="error",
                error="bad_resume_token",
            )
        # 取出后清掉，避免重复 resume；若再次缺参会重新 put
        self.pending_store.pop(session_id)
        run_mode: RunMode = pending.mode if pending.mode in ("react", "plan_execute") else self.mode  # type: ignore[assignment]
        skill_ids = list(pending.payload.get("skill_ids") or [])
        if not skill_ids:
            # resume 无 skill_ids 时仍走粘滞合并，避免补参继续时丢 travel
            skill_ids = self._skills_for_session(session_id, pending.user_input)
        else:
            # 把 pending 里的技能并回粘滞表（Redis 或进程 dict）
            if self._skills_store is not None:
                merged = merge_session_skills(
                    self._skills_store.get(session_id), skill_ids
                )
                self._skills_store.set(session_id, merged)
            else:
                self._session_skills[session_id] = merge_session_skills(
                    self._session_skills.get(session_id, []),
                    skill_ids,
                )
        tools = build_registry_for_skills(skill_ids)
        try:
            from travel_skill.shared import observability as travel_obs

            travel_obs.start_session(session_id)
        except Exception:  # noqa: BLE001
            logger.debug("travel_skill obs start_session 跳过", exc_info=True)
        logger.info(
            "resume 工具视图 session=%s skills=%s tools=%s",
            session_id,
            skill_ids or ["(none)"],
            tools.names(),
        )

        async def _go():
            if run_mode == "plan_execute":
                return await self.plan_loop.aresume(
                    session_id,
                    answers,
                    pending,
                    tools=tools,
                    skill_ids=skill_ids,
                )
            return await self.react_loop.aresume(
                session_id,
                answers,
                pending,
                tools=tools,
                skill_ids=skill_ids,
            )

        return await self._run_traced(
            session_id=session_id,
            user_id=user_id,
            run_mode=run_mode,
            coro_factory=_go,
            log_input=f"[resume] {answers!s}"[:200],
        )

    async def _run_traced(
        self,
        *,
        session_id: str,
        user_id: str,
        run_mode: RunMode,
        coro_factory,
        log_input: str,
    ) -> AgentRunResult:
        trace_id = new_trace_id()
        tracer = get_tracer()
        tracer.reset()
        ctx = TraceContext(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            agent_name=self.name,
            attrs={"mode": run_mode},
        )
        token = set_trace_context(ctx)
        logger.info("开始请求 mode=%s input=%s", run_mode, log_input[:200])
        get_metrics().incr("agent_requests_total", mode=run_mode)
        try:
            with tracer.span("agent.run", agent=self.name, mode=run_mode):
                result = await coro_factory()
            return result
        finally:
            clear_trace_context(token)

    def debug_snapshot(self, session_id: str) -> dict:
        root = get_tracer().root
        pending = self.pending_store.get(session_id)
        return {
            "session_id": session_id,
            "mode": self.mode,
            "pending": pending.public_dict() if pending else None,
            "memory": [
                {"role": r.role, "content": r.content, "meta": r.meta}
                for r in self.memory.get_all(session_id)
            ],
            "metrics": get_metrics().snapshot(),
            "trace": root.to_dict() if root else None,
        }

    async def astream(
        self,
        user_input: str,
        *,
        session_id: Optional[str] = None,
        user_id: str = "",
        mode: Optional[RunMode] = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式入口：日志/状态走 log|status，最终答案走 delta（单路多 event）。"""
        session_id = session_id or uuid.uuid4().hex
        run_mode: RunMode = mode or self.mode
        async for ev in self._astream_run(
            session_id=session_id,
            user_id=user_id,
            run_mode=run_mode,
            coro=self.arun(
                user_input,
                session_id=session_id,
                user_id=user_id,
                mode=run_mode,
            ),
            user_input=user_input,
        ):
            yield ev

    async def astream_resume(
        self,
        answers: Any,
        *,
        session_id: str,
        user_id: str = "",
        resume_token: str = "",
    ) -> AsyncIterator[StreamEvent]:
        """流式恢复 needs_input。"""
        pending = self.pending_store.get(session_id)
        run_mode: RunMode = self.mode
        if pending and pending.mode in ("react", "plan_execute"):
            run_mode = pending.mode  # type: ignore[assignment]
        async for ev in self._astream_run(
            session_id=session_id,
            user_id=user_id,
            run_mode=run_mode,
            coro=self.aresume(
                answers,
                session_id=session_id,
                user_id=user_id,
                resume_token=resume_token,
            ),
            user_input=f"[resume] {answers!s}"[:200],
        ):
            yield ev

    async def _astream_run(
        self,
        *,
        session_id: str,
        user_id: str,
        run_mode: RunMode,
        coro,
        user_input: str,
    ) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue = asyncio.Queue()
        token = set_stream_queue(queue)
        ensure_stream_logging()
        yield StreamEvent(
            event="meta",
            data={
                "session_id": session_id,
                "mode": run_mode,
                "user_id": user_id or "",
            },
        )
        emit_stream("status", phase="running", mode=run_mode)
        emit_log(
            f"开始运行 mode={run_mode} input={user_input[:120]}",
            level="INFO",
            source="runtime",
        )

        task = asyncio.create_task(coro)
        try:
            async for ev in iter_with_task(queue, task):
                yield ev
            result: AgentRunResult = task.result()
            for ev in self._events_from_result(result, run_mode=run_mode):
                yield ev
        except Exception as exc:  # noqa: BLE001
            logger.exception("astream 失败 session=%s", session_id)
            yield StreamEvent(
                event="error",
                data={"message": f"Agent 运行失败: {exc}"},
            )
        finally:
            reset_stream_queue(token)

    def _events_from_result(
        self,
        result: AgentRunResult,
        *,
        run_mode: RunMode,
    ) -> list[StreamEvent]:
        events: list[StreamEvent] = []
        # transcript 摘要进右侧日志，便于对照 CLI 落盘
        for i, item in enumerate(result.transcript or []):
            if not isinstance(item, dict):
                continue
            phase = item.get("phase") or item.get("step") or i
            tools = item.get("tools") or item.get("tool_calls")
            snippet = item.get("final_answer") or item.get("content") or ""
            if isinstance(snippet, str) and len(snippet) > 240:
                snippet = snippet[:237] + "..."
            msg = f"transcript[{phase}]"
            if tools:
                msg += f" tools={tools!r}"[:180]
            if snippet:
                msg += f" {snippet}"
            events.append(
                StreamEvent(
                    event="log",
                    data={
                        "level": "DEBUG",
                        "source": "transcript",
                        "message": msg[:2000],
                        "step": item.get("step"),
                    },
                )
            )

        if result.status == "needs_input":
            pending = result.pending or {}
            events.append(
                StreamEvent(
                    event="status",
                    data={"phase": "needs_input", "mode": run_mode},
                )
            )
            events.append(
                StreamEvent(
                    event="needs_input",
                    data={
                        "session_id": result.session_id,
                        "trace_id": result.trace_id,
                        "answer": result.answer,
                        "pending": pending,
                        "resume_token": pending.get("resume_token", ""),
                    },
                )
            )
            events.append(
                StreamEvent(
                    event="done",
                    data={
                        "session_id": result.session_id,
                        "trace_id": result.trace_id,
                        "status": result.status,
                        "answer": result.answer,
                        "steps": result.steps,
                        "mode": run_mode,
                    },
                )
            )
            return events

        answer = (result.answer or "").strip()
        if answer:
            events.append(
                StreamEvent(
                    event="status",
                    data={"phase": "answering", "mode": run_mode},
                )
            )
            # 主模型暂无 token 流：整段作为一次 delta，协议预留增量
            events.append(StreamEvent(event="delta", data={"content": answer}))

        events.append(
            StreamEvent(
                event="done",
                data={
                    "session_id": result.session_id,
                    "trace_id": result.trace_id,
                    "status": result.status,
                    "answer": answer,
                    "steps": result.steps,
                    "error": result.error or "",
                    "mode": run_mode,
                },
            )
        )
        if result.status == "error" and result.error:
            events.append(
                StreamEvent(
                    event="error",
                    data={"message": result.error},
                )
            )
        return events
