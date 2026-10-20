"""观测日志清理脚本的公共 CLI。

用法示例（由各专用脚本调用）::

    python -m agent.scripts.purge_transcript_logs --keep-days 3
    python -m agent.scripts.purge_metrics_logs --keep-days 7 --dry-run
    python -m agent.scripts.purge_trace_logs --keep-days 30 --list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def _ensure_repo_on_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_purge_cli(
    *,
    kind: str,
    default_keep_days: int,
    description: str,
    argv: Optional[list[str]] = None,
) -> int:
    _ensure_repo_on_path()
    from agent.observability.run_artifacts import (
        default_log_root,
        list_artifact_files,
        purge_artifact_files,
    )

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--keep-days",
        type=int,
        default=default_keep_days,
        help=f"保留最近 N 天（默认 {default_keep_days}）",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="",
        help="日志根目录（默认 agent/logs 或 AGENT_LOG_DIR）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出将删除的文件，不真正删除",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="只列出当前该类全部文件后退出",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 打印结果",
    )
    args = parser.parse_args(argv)

    log_root = Path(args.log_dir).expanduser() if args.log_dir else default_log_root()

    if args.list_only:
        files = list_artifact_files(kind, log_root=log_root)
        if args.json:
            print(json.dumps({"kind": kind, "files": [str(p) for p in files]}, ensure_ascii=False, indent=2))
        else:
            print(f"kind={kind} log_dir={log_root} count={len(files)}")
            for p in files:
                print(p)
        return 0

    report = purge_artifact_files(
        kind,
        keep_days=args.keep_days,
        log_root=log_root,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        action = "将删除" if args.dry_run else "已删除"
        print(
            f"kind={report['kind']} keep_days={report['keep_days']} "
            f"scanned={report['scanned']} kept={report['kept']} "
            f"{action}={report['deleted']} dry_run={report['dry_run']}"
        )
        for path in report["deleted_paths"]:
            print(f"  - {path}")
    return 0
