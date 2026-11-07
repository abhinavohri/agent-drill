from collections.abc import Sequence

from app.evaluations.internal.formatting import cost_label, join_words, outcome_label
from app.evaluations.internal.models import (
    CheckName,
    ResultStatus,
    RuleResult,
    RunResult,
    Verdict,
)

VERDICT_HEADINGS: dict[Verdict, str] = {
    Verdict.FAIL: "Failed",
    Verdict.REVIEW: "Waiting for review",
    Verdict.PASS: "Passed",
}


def render_batch_summary(results: Sequence[RunResult]) -> str:
    lines = [_headline(results), _release(results)]
    for verdict, heading in VERDICT_HEADINGS.items():
        group = sorted(
            (result for result in results if result.verdict is verdict),
            key=lambda result: result.scenario_id,
        )
        if group:
            lines.extend(("", f"{heading}:"))
            lines.extend(line for result in group for line in _run_lines(result))
    return "\n".join(lines) + "\n"


def _headline(results: Sequence[RunResult]) -> str:
    agents = join_words(sorted({f"{result.agent_id} {result.agent_version}" for result in results}))
    counts = ", ".join(
        f"{_count(results, verdict)} {heading.lower()}"
        for verdict, heading in VERDICT_HEADINGS.items()
    )
    runs = "run" if len(results) == 1 else "runs"
    headline = f"{agents}: {len(results)} {runs}. {counts}."
    costs = [
        result.metrics.total_cost_usd
        for result in results
        if result.metrics is not None and result.metrics.total_cost_usd is not None
    ]
    if costs:
        headline = f"{headline} Cost {cost_label(sum(costs))}."
    return headline


def _release(results: Sequence[RunResult]) -> str:
    failed = _count(results, Verdict.FAIL)
    if failed:
        blocks = _approval_messages(results, ResultStatus.FAILED)
        return " ".join((f"Release: blocked. {failed} of {len(results)} failed.", *blocks))
    if _count(results, Verdict.REVIEW):
        return "Release: waiting for review."
    return " ".join(("Release: approved.", *_approval_messages(results, ResultStatus.PASSED)))


def _run_lines(result: RunResult) -> list[str]:
    lines = [f"- {result.scenario_id}: {outcome_label(result.outcome)}"]
    lines.extend(f"  - {rule.rule_id}: {rule.message}" for rule in _open_issues(result))
    return lines


def _open_issues(result: RunResult) -> tuple[RuleResult, ...]:
    if result.verdict is Verdict.FAIL:
        return result.failed_rules()
    if result.verdict is Verdict.REVIEW:
        return result.rules_with_status(ResultStatus.OPEN)
    return ()


def _approval_messages(results: Sequence[RunResult], status: ResultStatus) -> list[str]:
    return sorted(
        {
            rule.message
            for result in results
            for check in result.checks
            if check.check is CheckName.HUMAN_APPROVAL
            for rule in check.rules
            if rule.status is status
        }
    )


def _count(results: Sequence[RunResult], verdict: Verdict) -> int:
    return sum(1 for result in results if result.verdict is verdict)
