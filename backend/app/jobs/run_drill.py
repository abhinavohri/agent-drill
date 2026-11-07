"""Run one target-independent command drill."""

import argparse
import sys
from pathlib import Path

from app.drills.facade import (
    CommandDrillRunner,
    DrillConfigError,
    DrillRunStatus,
    TargetRunContext,
    load_command_config,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_command_config(args.config)
    except DrillConfigError as exc:
        parser.error(str(exc))
    result = CommandDrillRunner(config).run(
        TargetRunContext(
            scenario_id=args.scenario,
            task=args.task,
            mcp_url=args.mcp_url,
            trace_path=args.trace_path,
            policy_file=args.policy_file,
        )
    )
    content = result.model_dump_json(indent=2, exclude_none=True) + "\n"
    try:
        if args.output is None:
            sys.stdout.write(content)
        else:
            args.output.write_text(content)
    except OSError as exc:
        parser.error(f"Cannot write drill result: {exc}")
    return 0 if result.status is DrillRunStatus.COMPLETED else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.jobs.run_drill",
        description="Run one target command and validate its ATIF trace.",
    )
    parser.add_argument("config", type=Path, help="command-runner configuration JSON")
    parser.add_argument("scenario", help="scenario identifier")
    parser.add_argument("--task", help="complete task text for the target agent")
    parser.add_argument("--mcp-url", help="streamable HTTP MCP URL")
    parser.add_argument("--trace-path", type=Path, help="override the configured ATIF path")
    parser.add_argument("--policy-file", type=Path, help="policy text supplied to the target")
    parser.add_argument("--output", type=Path, help="write the drill result JSON here")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
