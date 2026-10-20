"""终端调试入口。

用法：
    python -m agent
    python -m agent --mode plan_execute --once "现在几点？并算 (1+2)*3"
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path


def _load_dotenv() -> None:
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        load_dotenv()
    except ImportError:
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in __import__("os").environ:
                __import__("os").environ[key] = val


def _print_banner(session_id: str, tools: list[str], mode: str) -> None:
    print("=" * 60)
    print(" Agent CLI — 终端调试")
    print("=" * 60)
    print(f" mode       = {mode}")
    print(f" session_id = {session_id}")
    print(f" 可用工具   = {', '.join(tools)}")
    print(" 命令: /quit | /memory | /metrics | /trace | /clear | /pending")
    print("       /mode react | /mode plan_execute")
    print(" 缺参时会暂停并一次询问多项，直接回复即可继续。")
    print(" 每轮默认写出 transcript/trace/metrics 到 agent/logs/。")
    print("=" * 60)


def _maybe_save_artifacts(result, *, mode: str, enabled: bool) -> None:
    """把本轮 transcript / trace / metrics 落到三个 JSON 文件。"""
    if not enabled or result is None:
        return
    from agent.observability.run_artifacts import save_run_artifacts

    paths = save_run_artifacts(result, mode=mode)
    print(
        f"[artifacts] transcript={paths.transcript}\n"
        f"            trace={paths.trace}\n"
        f"            metrics={paths.metrics}"
    )


def _handle_needs_input(
    agent,
    session_id: str,
    result,
    show_transcript: bool,
    *,
    mode: str = "",
    save_artifacts: bool = True,
) -> object:
    """CLI：一次问多项 → resume；可循环直到不再 needs_input。"""
    # 首次缺参也落盘，便于对照当时的 transcript / gaps
    _maybe_save_artifacts(result, mode=mode, enabled=save_artifacts)
    while result.status == "needs_input":
        pending = result.pending or {}
        questions = pending.get("questions") or []
        print(f"\n助手> {result.answer}")
        print(
            f"(status=needs_input source={pending.get('source')} "
            f"trace_id={result.trace_id})"
        )
        if questions:
            print("--- 请补充 ---")
            for q in questions:
                print(f"  [{q.get('id')}] {q.get('prompt')}")
        try:
            answers = input("\n补参> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消补参。")
            return result
        if not answers:
            print("未输入内容，已取消本次补参。")
            return result
        if answers in ("/quit", "/exit", "quit", "exit"):
            return result
        result = agent.resume(
            answers,
            session_id=session_id,
            resume_token=str(pending.get("resume_token") or ""),
        )
        _maybe_save_artifacts(result, mode=mode, enabled=save_artifacts)
        if show_transcript or result.status not in ("ok", "needs_input"):
            print("--- transcript ---")
            print(json.dumps(result.transcript, ensure_ascii=False, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from agent.main_agent import MainAgent
    from agent.observability.logging_setup import setup_logging
    from agent.observability.metrics import get_metrics

    parser = argparse.ArgumentParser(description="Agent 终端调试")
    parser.add_argument("--once", type=str, default="", help="单次提问后退出")
    parser.add_argument("--session", type=str, default="", help="指定 session_id")
    parser.add_argument("--max-steps", type=int, default=8, help="ReAct 最大步数")
    parser.add_argument("--max-replans", type=int, default=2, help="Plan-Execute 最大重规划次数")
    parser.add_argument(
        "--mode",
        type=str,
        default="",
        choices=["", "react", "plan_execute"],
        help="运行模式（默认 env AGENT_RUN_MODE 或 react）",
    )
    parser.add_argument("--log-level", type=str, default="INFO", help="日志级别")
    parser.add_argument(
        "--show-transcript",
        action="store_true",
        help="打印逐步 transcript",
    )
    parser.add_argument(
        "--no-save-artifacts",
        action="store_true",
        help="不写 agent/logs 下的 transcript/trace/metrics 文件",
    )
    args = parser.parse_args(argv)

    setup_logging(args.log_level)
    mode = args.mode or None
    agent = MainAgent(
        max_steps=args.max_steps,
        max_replans=args.max_replans,
        mode=mode,  # type: ignore[arg-type]
    )
    session_id = args.session or uuid.uuid4().hex[:12]
    current_mode = agent.mode
    save_artifacts = not args.no_save_artifacts

    if args.once:
        return _run_once(
            agent,
            session_id,
            args.once,
            args.show_transcript,
            current_mode,
            save_artifacts=save_artifacts,
        )

    _print_banner(session_id, agent.tools.names(), current_mode)
    while True:
        try:
            user_input = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return 0

        if not user_input:
            continue

        if user_input in ("/quit", "/exit", "quit", "exit"):
            print("再见。")
            return 0
        if user_input in ("/help", "help"):
            _print_banner(session_id, agent.tools.names(), current_mode)
            continue
        if user_input.startswith("/mode"):
            parts = user_input.split()
            if len(parts) == 1:
                print(f"当前 mode={current_mode}")
            elif parts[1] in ("react", "plan_execute"):
                current_mode = parts[1]  # type: ignore[assignment]
                agent.mode = current_mode  # type: ignore[assignment]
                print(f"已切换 mode={current_mode}")
            else:
                print("用法: /mode react | /mode plan_execute")
            continue
        if user_input == "/memory":
            print(json.dumps(agent.debug_snapshot(session_id)["memory"], ensure_ascii=False, indent=2))
            continue
        if user_input == "/metrics":
            print(json.dumps(get_metrics().snapshot(), ensure_ascii=False, indent=2))
            continue
        if user_input == "/trace":
            print(json.dumps(agent.debug_snapshot(session_id)["trace"], ensure_ascii=False, indent=2))
            continue
        if user_input == "/pending":
            print(json.dumps(agent.debug_snapshot(session_id).get("pending"), ensure_ascii=False, indent=2))
            continue
        if user_input == "/clear":
            agent.memory.clear(session_id)
            agent.pending_store.clear(session_id)
            print(f"已清空会话记忆与 pending: {session_id}")
            continue

        # 若上一轮挂起，普通输入视为补参
        if agent.pending_store.get(session_id) is not None:
            pending = agent.pending_store.get(session_id)
            result = agent.resume(
                user_input,
                session_id=session_id,
                resume_token=pending.resume_token if pending else "",
            )
        else:
            result = agent.run(user_input, session_id=session_id, mode=current_mode)

        if result.status == "needs_input":
            result = _handle_needs_input(
                agent,
                session_id,
                result,
                args.show_transcript,
                mode=current_mode,
                save_artifacts=save_artifacts,
            )
        else:
            _maybe_save_artifacts(
                result, mode=current_mode, enabled=save_artifacts
            )

        print(f"\n助手> {result.answer}")
        print(
            f"(mode={current_mode} status={result.status} steps={result.steps} "
            f"trace_id={result.trace_id})"
        )
        if args.show_transcript or result.status not in ("ok", "needs_input"):
            print("--- transcript ---")
            print(json.dumps(result.transcript, ensure_ascii=False, indent=2))

    return 0


def _run_once(
    agent,
    session_id: str,
    question: str,
    show_transcript: bool,
    mode: str,
    *,
    save_artifacts: bool = True,
) -> int:
    result = agent.run(question, session_id=session_id, mode=mode)  # type: ignore[arg-type]
    if result.status == "needs_input":
        # --once 非交互：打印缺口后以非 0 退出，便于脚本探测
        _maybe_save_artifacts(result, mode=mode, enabled=save_artifacts)
        print(result.answer)
        print(
            json.dumps(result.pending, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 2
    _maybe_save_artifacts(result, mode=mode, enabled=save_artifacts)
    print(result.answer)
    print(
        f"\n[debug] mode={mode} status={result.status} steps={result.steps} "
        f"trace_id={result.trace_id} session_id={session_id}",
        file=sys.stderr,
    )
    if show_transcript:
        print(json.dumps(result.transcript, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
