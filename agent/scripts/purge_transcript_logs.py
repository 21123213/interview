"""清理 transcript 观测文件。默认保留 3 天。

用法::

    python -m agent.scripts.purge_transcript_logs
    python -m agent.scripts.purge_transcript_logs --keep-days 3 --dry-run
    python -m agent.scripts.purge_transcript_logs --list
"""

from __future__ import annotations

from agent.scripts.purge_common import run_purge_cli


def main(argv: list[str] | None = None) -> int:
    return run_purge_cli(
        kind="transcript",
        default_keep_days=3,
        description="清理 agent/logs/transcript（默认保留 3 天）",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
