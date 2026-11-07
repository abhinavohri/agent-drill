import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from app.evaluations.facade import (
    EvaluationInputError,
    RecordedRun,
    ReviewInput,
    RunMetrics,
    RunResult,
    evaluate_run,
    render_batch_summary,
    render_run_report,
)
from app.workflows.facade import (
    LibraryError,
    ScenarioLibrary,
    UnknownRecordError,
    load_scenario_library,
)

LIBRARY_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "refunds"
RECORDED_RUN = "recorded-run.json"
RESULT = "result.json"
REPORT = "report.md"
SUMMARY = "summary.md"
INPUT_ERRORS = (OSError, ValidationError, LibraryError, UnknownRecordError, EvaluationInputError)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    runs = sorted(path.parent for path in args.batch.rglob(RECORDED_RUN))
    if not runs:
        parser.error(f"{args.batch} contains no {RECORDED_RUN} files")
    try:
        library = load_scenario_library(args.library)
        review = ReviewInput()
        if args.review is not None:
            review = ReviewInput.model_validate_json(args.review.read_text())
        results = tuple(_grade(library, run, review) for run in runs)
    except INPUT_ERRORS as exc:
        parser.error(str(exc))
    summary = render_batch_summary(results)
    (args.batch / SUMMARY).write_text(summary)
    sys.stdout.write(summary)
    return 0


def _grade(library: ScenarioLibrary, run: Path, review: ReviewInput) -> RunResult:
    recorded = RecordedRun.model_validate_json((run / RECORDED_RUN).read_text())
    scenario = library.scenario(recorded.run.scenario_id)
    workflow = library.workflow(recorded.workflow_id)
    result = evaluate_run(workflow, scenario, recorded, review, metrics=_drill_metrics(run))
    (run / RESULT).write_text(result.model_dump_json(indent=2) + "\n")
    (run / REPORT).write_text(render_run_report(result, recorded, scenario))
    return result


def _drill_metrics(run: Path) -> RunMetrics | None:
    previous = run / RESULT
    if not previous.exists():
        return None
    return RunResult.model_validate_json(previous.read_text()).metrics


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.jobs.review_drills",
        description=(
            "Grade every recorded drill run in a batch directory with the team's review "
            "decisions, rewrite each result and report, and print the batch summary."
        ),
    )
    parser.add_argument("batch", type=Path, help="directory that contains the drill outputs")
    parser.add_argument("--review", type=Path, help="reviewer decisions JSON for the release")
    parser.add_argument("--library", type=Path, default=LIBRARY_ROOT, help="scenario library root")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
