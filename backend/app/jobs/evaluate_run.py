import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from app.evaluations.facade import (
    ComparisonError,
    EvaluationInputError,
    RecordedRun,
    ReviewInput,
    RunResult,
    compare_results,
    evaluate_run,
    render_comparison,
    render_run_report,
)
from app.workflows.facade import (
    LibraryError,
    ScenarioLibrary,
    UnknownRecordError,
    load_scenario_library,
)

LIBRARY_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "refunds"
INPUT_ERRORS = (
    OSError,
    ValidationError,
    LibraryError,
    UnknownRecordError,
    EvaluationInputError,
    ComparisonError,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        library = load_scenario_library(args.library)
        recorded = RecordedRun.model_validate_json(args.run.read_text())
        review = ReviewInput()
        if args.review is not None:
            review = ReviewInput.model_validate_json(args.review.read_text())
        result = _evaluate(library, recorded, review)
        report = render_run_report(result, recorded, library.scenario(recorded.run.scenario_id))
        if args.compare_with is not None:
            original_run = RecordedRun.model_validate_json(args.compare_with.read_text())
            original = _evaluate(library, original_run, ReviewInput())
            report = f"{report}\n{render_comparison(compare_results(original, result))}"
    except INPUT_ERRORS as exc:
        parser.error(str(exc))
    if args.result_json is not None:
        args.result_json.write_text(result.model_dump_json(indent=2) + "\n")
    if args.report is not None:
        args.report.write_text(report)
    else:
        sys.stdout.write(report)
    return 0


def _evaluate(library: ScenarioLibrary, recorded: RecordedRun, review: ReviewInput) -> RunResult:
    workflow = library.workflow(recorded.workflow_id)
    scenario = library.scenario(recorded.run.scenario_id)
    return evaluate_run(workflow, scenario, recorded, review)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.jobs.evaluate_run",
        description="Evaluate a saved Agent Drill run and write its Markdown report.",
    )
    parser.add_argument("run", type=Path, help="saved run JSON")
    parser.add_argument("--review", type=Path, help="reviewer decisions JSON")
    parser.add_argument("--compare-with", type=Path, help="saved JSON of the original run")
    parser.add_argument("--result-json", type=Path, help="write the RunResult JSON here")
    parser.add_argument("--report", type=Path, help="write the Markdown report here")
    parser.add_argument("--library", type=Path, default=LIBRARY_ROOT, help="scenario library root")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
