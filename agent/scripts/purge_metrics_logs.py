"""清理 metrics 观测文件。默认保留 7 天（约一周）。

用法::

    python -m agent.scripts.purge_metrics_logs
    python -m agent.scripts.purge_metrics_logs --keep-days 7 --dry-run
    python -m agent.scripts.purge_metrics_logs --list
"""

from __future__ import annotations

from agent.scripts.purge_common import run_purge_cli


def main(argv: list[str] | None = None) -> int:
    return run_purge_cli(
        kind="metrics",
        default_keep_days=7,
        description="清理 agent/logs/metrics（默认保留 7 天）",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
