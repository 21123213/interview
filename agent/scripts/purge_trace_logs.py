"""清理 trace 观测文件。默认保留 30 天（约一个月）。

用法::

    python -m agent.scripts.purge_trace_logs
    python -m agent.scripts.purge_trace_logs --keep-days 30 --dry-run
    python -m agent.scripts.purge_trace_logs --list
"""

from __future__ import annotations

from agent.scripts.purge_common import run_purge_cli


def main(argv: list[str] | None = None) -> int:
    return run_purge_cli(
        kind="trace",
        default_keep_days=30,
        description="清理 agent/logs/trace（默认保留 30 天）",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
