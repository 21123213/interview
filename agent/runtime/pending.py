"""缺参暂停：问题组装、回答解析、会话级 pending（不阻塞其它会话）。

典型流程：
1. 工具缺参 → questions_from_gaps 生成问题 → compose_user_answer 展示给用户
2. PendingStore.put 按 session 挂起当前运行
3. 用户回复 → parse_user_answers 解析 → merge_answers_into_args 写回工具参数 → 继续跑
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent.runtime.param_check import ParamGap, SourceKind

logger = logging.getLogger("agent.runtime.pending")


@dataclass
class AskQuestion:
    """一条给人看的确认项；field 仅给 resume 合并用。

    id: 问题编号（如 q1），解析回答时可用
    field: 对应工具参数名；特殊值 _continue 表示「继续/换方式」，不写进参数
    prompt: 展示给用户的问句
    tool / call_id: 关联哪次工具调用（多工具时用来过滤）
    """

    id: str
    field: str
    prompt: str
    tool: str = ""
    call_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化，供 API / transcript 返回给前端。"""
        return {
            "id": self.id,
            "field": self.field,
            "prompt": self.prompt,
            "tool": self.tool,
            "call_id": self.call_id,
        }


@dataclass
class PendingState:
    """某 session 上未完成的一次运行（进程内；API 同样按 session 取）。

    mode: 运行模式（如 chat / plan）
    source: 缺参来源（user_gap / upstream_gap）
    questions: 待用户回答的问题列表
    user_input: 触发本次缺参时的用户原文
    resume_token: 恢复凭证，防止误恢复错误会话
    payload: 挂起时需要暂存的运行上下文（工具调用、中间状态等）
    """

    mode: str
    source: SourceKind
    questions: List[AskQuestion]
    user_input: str = ""
    resume_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    payload: Dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> Dict[str, Any]:
        """对外可返回的字段（不含 payload 等内部状态）。"""
        return {
            "source": self.source,
            "resume_token": self.resume_token,
            "questions": [q.to_dict() for q in self.questions],
            "mode": self.mode,
        }


class PendingStore:
    """按 session_id 隔离的内存挂起表。

    并发用户各写各的；用锁保证线程安全。
    put → 挂起；get → 查看；pop/clear → 恢复或取消后清掉。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # session_id → 该会话当前挂起的状态（同一会话同时只保留一份）
        self._items: Dict[str, PendingState] = {}

    def put(self, session_id: str, state: PendingState) -> None:
        """写入/覆盖该会话的挂起状态（新缺参会盖掉旧的）。"""
        with self._lock:
            self._items[session_id] = state

    def get(self, session_id: str) -> Optional[PendingState]:
        """只读取出；不存在则返回 None。"""
        with self._lock:
            return self._items.get(session_id)

    def pop(self, session_id: str) -> Optional[PendingState]:
        """取出并删除（resume 成功后用，避免重复恢复）。"""
        with self._lock:
            return self._items.pop(session_id, None)

    def clear(self, session_id: str) -> None:
        """丢弃挂起（用户取消 / 新请求覆盖前清理）。"""
        with self._lock:
            self._items.pop(session_id, None)


# 用户可见字段的中文名（避免暴露英文参数）
_FIELD_LABELS_ZH: Dict[str, str] = {
    "destination": "目的地",
    "origin": "出发地",
    "start_date": "出发日期",
    "check_in_date": "入住日期",
    "stay_nights": "入住晚数",
    "days": "游玩天数",
    "season": "季节偏好",
    "tier": "酒店档次偏好（经济/舒适/豪华）",
    "extra_context": "其他偏好或备注",
    "keyword": "搜索关键词",
}


def _prompt_for_field(gap: ParamGap, field_name: str, field_desc: str) -> str:
    """根据 schema 描述生成单字段问句；不用裸英文参数名问用户。"""
    desc = (field_desc or "").strip()
    if desc and desc != field_name and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", desc):
        return desc.rstrip("。.?？") + "？"
    label = _FIELD_LABELS_ZH.get(field_name) or ""
    if label:
        return f"请补充{label}？"
    # 仍是内部英文字段：不直接甩给用户
    return "还需要一点信息才能继续，请补充您的出行偏好？"


def questions_from_gaps(gaps: List[ParamGap]) -> List[AskQuestion]:
    """把 ParamGap 列表转成给用户看的 AskQuestion 列表。

    - user_gap：每个缺字段一条问题（用中文描述做人话）
    - upstream_gap：上游工具没结果，只生成一条概括问句（field=_continue），
      不暴露内部字段名；多个 upstream 也只问一次
    """
    questions: List[AskQuestion] = []
    saw_upstream = False
    n = 0
    for gap in gaps:
        if gap.source == "upstream_gap":
            # 上游失败只提示一次，避免刷屏
            if saw_upstream:
                continue
            saw_upstream = True
            n += 1
            # 按缺口字段微调问句，避免 daily_routes 缺失时误问「住哪个区」
            field_names = {f.field for f in gap.fields}
            if gap.tool == "plan_transport" and (
                "daily_routes" in field_names or field_names & {"itinerary_lines", "loose_pois"}
            ):
                tool_hint = "行程日程还不完整，接驳没法排。请再说几个必去景点或区域，我重新编排后再算交通。"
            elif gap.tool == "plan_transport":
                tool_hint = "市内交通还差住宿位置信息，我可以先按行程首站估算接驳；也可以告诉我希望住在哪个区域。"
            else:
                tool_hint = {
                    "search_stay": "还没找到合适酒店。可以说一下更倾向的区域或档次，我再帮你查。",
                    "build_route": "行程点位还不完整。可以说一下必去景点，我重新编排。",
                }.get(
                    gap.tool,
                    "刚才没拿到继续安排所需的结果，可以说一下偏好，我换种方式再试。",
                )
            questions.append(
                AskQuestion(
                    id=f"q{n}",
                    field="_continue",
                    prompt=tool_hint,
                    tool=gap.tool,
                    call_id=gap.call_id,
                )
            )
            continue
        # 用户侧缺参：按字段拆成多问
        for f in gap.fields:
            n += 1
            questions.append(
                AskQuestion(
                    id=f"q{n}",
                    field=f.field,
                    prompt=_prompt_for_field(gap, f.field, f.description),
                    tool=gap.tool,
                    call_id=gap.call_id,
                )
            )
    return questions


def compose_user_answer(questions: List[AskQuestion], source: SourceKind) -> str:
    """把问题列表拼成一段给用户看的总述（不出现工具名）。

    单问一句；多问编号列表，并提示可一行说完或按编号回答。
    """
    if source == "upstream_gap":
        return questions[0].prompt if questions else "目前还缺一些信息才能继续，请补充你的具体需求。"
    if not questions:
        return "还需要一些信息才能继续，请补充。"
    if len(questions) == 1:
        return f"还需要确认：{questions[0].prompt}"
    lines = ["还需要确认以下几项："]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q.prompt}")
    lines.append("可以一行说完，或按编号分行回答。")
    return "\n".join(lines)


def parse_user_answers_rules(questions: List[AskQuestion], raw: Any) -> Dict[str, str]:
    """规则解析用户回复为 {question.id / field → 答案}（同步、无 LLM）。

    支持多种输入形态（按优先级尝试）：
    1. 已是 dict（前端结构化提交）
    2. JSON 字符串
    3. 只有一问：整段当作该问答案
    4. 编号回答：如「1. 北京\\n2. 明天」
    5. 分隔符拆分：换行 / 分号 / 逗号，段数够则按顺序对齐
    6. 拆不开：整段先填第一问（resume 后若仍缺会再问）

    生产路径请用 answer_parser.aparse_user_answers（规则 + fast 模型抽取）。
    """
    # 1) 结构化 dict
    if isinstance(raw, dict):
        out: Dict[str, str] = {}
        for k, v in raw.items():
            if v is None:
                continue
            out[str(k)] = str(v).strip()
        return out
    text = str(raw or "").strip()
    if not text:
        return {}
    # 2) 尝试当 JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {str(k): str(v).strip() for k, v in data.items() if v is not None}
    except json.JSONDecodeError:
        pass

    # 3) 单问题：整段即答案（同时挂到 id 和 field，方便后面按任一键取）
    if len(questions) == 1:
        q = questions[0]
        return {q.id: text, q.field: text}

    # 4) 「1. xxx」「2) yyy」这类编号行
    numbered: Dict[int, str] = {}
    for m in re.finditer(
        r"(?:^|\n)\s*(?:(\d+)[\.\)、:：]\s*)(.+)",
        text,
    ):
        numbered[int(m.group(1))] = m.group(2).strip()
    if numbered:
        out = {}
        for i, q in enumerate(questions, 1):
            if i in numbered:
                out[q.id] = numbered[i]
                out[q.field] = numbered[i]
        if out:
            return out

    # 5) 用常见分隔符按顺序切分
    parts = [p.strip() for p in re.split(r"[\n；;，,]+", text) if p.strip()]
    if len(parts) >= len(questions):
        out = {}
        for q, p in zip(questions, parts):
            out[q.id] = p
            out[q.field] = p
        return out

    # 6) 拆不开：整段先填第一问，resume 后若仍缺会再问
    q0 = questions[0]
    return {q0.id: text, q0.field: text}


def parse_user_answers(questions: List[AskQuestion], raw: Any) -> Dict[str, str]:
    """parse_user_answers_rules 的别名，供测试与离线场景。"""
    return parse_user_answers_rules(questions, raw)


def record_needs_input(
    transcript: List[Dict[str, Any]],
    *,
    mode: str,
    source: SourceKind,
    gaps: List[ParamGap],
    questions: List[AskQuestion],
) -> None:
    """缺参时打点：logger + metrics + trace span + transcript，便于排查与统计。

    四者互补，不是同一份数据拷贝。
    """
    from agent.observability.metrics import get_metrics
    from agent.observability.tracer import get_tracer

    tools = sorted({g.tool for g in gaps})
    fields = [f.field for g in gaps for f in g.fields]
    logger.info(
        "needs_input mode=%s source=%s tools=%s fields=%s",
        mode,
        source,
        ",".join(tools),
        ",".join(fields),
    )
    get_metrics().incr("needs_input_total", source=source, mode=mode)
    sp = get_tracer().current
    if sp is not None:
        sp.add_event(
            "needs_input",
            source=source,
            tools=",".join(tools),
            fields=",".join(fields),
            mode=mode,
        )
        sp.status = "needs_input"
    transcript.append(
        {
            "phase": "needs_input",
            "source": source,
            "tools": tools,
            "fields": fields,
            "questions": [q.to_dict() for q in questions],
        }
    )


def merge_answers_into_args(
    arguments: Dict[str, Any],
    questions: List[AskQuestion],
    answers: Dict[str, str],
    call_id: str,
) -> Dict[str, Any]:
    """把用户答案合并进某次工具调用的 arguments，返回新 dict（不改原对象）。

    只处理 call_id 匹配的问题。
    - 普通 field：直接写入 arguments[field]
    - `_continue`：追加到 extra_context（upstream_gap 追问的偏好/区域等）
    取值顺序：answers[q.id] → answers[field] → answers["call_id.field"]。
    """
    merged = dict(arguments)
    for q in questions:
        # 多工具并行时，只合并属于当前 call 的答案
        if q.call_id and q.call_id != call_id:
            continue
        val = answers.get(q.id) or answers.get(q.field) or answers.get(f"{call_id}.{q.field}")
        if not val:
            continue
        if q.field.startswith("_"):
            # upstream 概括追问：不落英文字段名，写入 extra_context 供工具/重规划使用
            if q.field == "_continue":
                prev = str(merged.get("extra_context") or "").strip()
                note = f"用户补充：{val}"
                merged["extra_context"] = f"{prev}\n{note}".strip() if prev else note
            continue
        merged[q.field] = val
    return merged
