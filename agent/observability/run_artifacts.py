"""把一次 Agent 运行的 transcript / trace / metrics 落到三个文件。

目录约定（相对仓库根，可用 AGENT_LOG_DIR 覆盖）::

    agent/logs/
      transcript/YYYYMMDD/HHMMSS_<trace12>_<session12>.json
      trace/YYYYMMDD/HHMMSS_<trace12>_<session12>.json
      metrics/YYYYMMDD/HHMMSS_<trace12>_<session12>.json

每个文件统一外壳（schema=agent.run_artifact.v1），真实内容在 payload。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from agent.observability.metrics import get_metrics
from agent.runtime.result import AgentRunResult

logger = logging.getLogger("agent.observability.run_artifacts")

SCHEMA = "agent.run_artifact.v1"
KINDS = ("transcript", "trace", "metrics")


def default_log_root() -> Path:
    """默认日志根目录：agent/logs（可用环境变量 AGENT_LOG_DIR 覆盖）。"""
    env = (os.getenv("AGENT_LOG_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "logs"


@dataclass
class ArtifactPaths:
    transcript: Path
    trace: Path
    metrics: Path

    def as_dict(self) -> Dict[str, str]:
        return {
            "transcript": str(self.transcript),
            "trace": str(self.trace),
            "metrics": str(self.metrics),
        }


def _stamp_parts(now: Optional[datetime] = None) -> tuple[str, str]:
    dt = now or datetime.now().astimezone()
    return dt.strftime("%Y%m%d"), dt.strftime("%H%M%S")


def _safe_id(value: str, n: int = 12) -> str:
    text = (value or "unknown").strip() or "unknown"
    return text[:n]


def _envelope(
    *,
    kind: str,
    result: AgentRunResult,
    mode: str,
    payload: Any,
    saved_at: datetime,
) -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "kind": kind,
        "saved_at": saved_at.isoformat(timespec="seconds"),
        "trace_id": result.trace_id,
        "session_id": result.session_id,
        "mode": mode,
        "status": result.status,
        "steps": result.steps,
        "error": result.error or "",
        "user_input": result.user_input or "",
        "payload": payload,
    }


def _write_json(path: Path, data: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def save_run_artifacts(
    result: AgentRunResult,
    *,
    mode: str = "",
    log_root: Optional[Path] = None,
    metrics_snapshot: Optional[Dict[str, Any]] = None,
) -> ArtifactPaths:
    """按统一格式写出 transcript / trace / metrics 三个 JSON 文件。"""
    root = Path(log_root) if log_root is not None else default_log_root()
    day, hms = _stamp_parts()
    saved_at = datetime.now().astimezone()
    stem = f"{hms}_{_safe_id(result.trace_id)}_{_safe_id(result.session_id)}.json"

    transcript_payload: List[Dict[str, Any]] = list(result.transcript or [])
    if result.user_input and not (
        transcript_payload
        and transcript_payload[0].get("phase") == "user"
    ):
        transcript_payload = [
            {"phase": "user", "content": result.user_input},
            *transcript_payload,
        ]
    trace_payload = result.trace_tree
    if trace_payload is None:
        # 请求结束后 ContextVar 栈已空，回退 last_root
        from agent.observability.tracer import get_tracer

        root_span = get_tracer().root
        trace_payload = root_span.to_dict() if root_span else None

    metrics_payload = (
        metrics_snapshot
        if metrics_snapshot is not None
        else get_metrics().snapshot()
    )

    paths = ArtifactPaths(
        transcript=_write_json(
            root / "transcript" / day / stem,
            _envelope(
                kind="transcript",
                result=result,
                mode=mode,
                payload=transcript_payload,
                saved_at=saved_at,
            ),
        ),
        trace=_write_json(
            root / "trace" / day / stem,
            _envelope(
                kind="trace",
                result=result,
                mode=mode,
                payload=trace_payload,
                saved_at=saved_at,
            ),
        ),
        metrics=_write_json(
            root / "metrics" / day / stem,
            _envelope(
                kind="metrics",
                result=result,
                mode=mode,
                payload=metrics_payload,
                saved_at=saved_at,
            ),
        ),
    )
    logger.info(
        "run_artifacts saved transcript=%s trace=%s metrics=%s",
        paths.transcript,
        paths.trace,
        paths.metrics,
    )
    return paths


def list_artifact_files(
    kind: str,
    *,
    log_root: Optional[Path] = None,
) -> List[Path]:
    """列出某类观测文件（递归 *.json）。"""
    if kind not in KINDS:
        raise ValueError(f"kind 必须是 {KINDS} 之一，收到: {kind}")
    root = Path(log_root) if log_root is not None else default_log_root()
    base = root / kind
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.json") if p.is_file())


def purge_artifact_files(
    kind: str,
    *,
    keep_days: int,
    log_root: Optional[Path] = None,
    dry_run: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """按修改时间删除超过 keep_days 的文件；返回统计。"""
    if keep_days < 0:
        raise ValueError("keep_days 不能为负")
    files = list_artifact_files(kind, log_root=log_root)
    cutoff = (now or datetime.now(timezone.utc)).timestamp() - keep_days * 86400
    kept: List[str] = []
    deleted: List[str] = []
    for path in files:
        mtime = path.stat().st_mtime
        if mtime < cutoff:
            deleted.append(str(path))
            if not dry_run:
                path.unlink(missing_ok=True)
        else:
            kept.append(str(path))

    # 清理空日期目录
    root = Path(log_root) if log_root is not None else default_log_root()
    kind_root = root / kind
    if kind_root.is_dir() and not dry_run:
        for day_dir in sorted(kind_root.iterdir(), reverse=True):
            if day_dir.is_dir() and not any(day_dir.iterdir()):
                day_dir.rmdir()

    return {
        "kind": kind,
        "keep_days": keep_days,
        "dry_run": dry_run,
        "scanned": len(files),
        "kept": len(kept),
        "deleted": len(deleted),
        "deleted_paths": deleted,
    }
