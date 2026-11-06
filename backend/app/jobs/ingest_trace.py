"""Validate and normalize one ATIF trajectory file."""

import argparse
import sys
from pathlib import Path

from app.traces.facade import TraceInputError, load_atif


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        trajectory = load_atif(args.trace)
    except TraceInputError as exc:
        parser.error(str(exc))
    content = trajectory.model_dump_json(indent=2, exclude_none=True) + "\n"
    try:
        if args.output is None:
            sys.stdout.write(content)
        else:
            args.output.write_text(content)
    except OSError as exc:
        parser.error(f"Cannot write trace output: {exc}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.jobs.ingest_trace",
        description="Validate one ATIF v1.7 trajectory and write normalized JSON.",
    )
    parser.add_argument("trace", type=Path, help="ATIF trajectory JSON")
    parser.add_argument("--output", type=Path, help="write normalized ATIF JSON here")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
