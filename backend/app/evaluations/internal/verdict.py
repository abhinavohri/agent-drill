from collections.abc import Iterable, Sequence

from app.evaluations.internal.models import (
    CheckName,
    CheckResult,
    ResultStatus,
    RuleResult,
    Tier,
    Verdict,
)

CHECK_TIERS: dict[CheckName, Tier] = {
    CheckName.INPUT_SCHEMA: Tier.HARD,
    CheckName.TOOL_PERMISSIONS: Tier.HARD,
    CheckName.ACTION_ORDER: Tier.HARD,
    CheckName.FINAL_STATE: Tier.HARD,
    CheckName.SEMANTIC_OUTPUT: Tier.REVIEW,
    CheckName.HUMAN_APPROVAL: Tier.REVIEW,
}
STATUS_PRECEDENCE = (ResultStatus.FAILED, ResultStatus.OPEN, ResultStatus.PASSED)


def group_checks(results: Sequence[RuleResult]) -> tuple[CheckResult, ...]:
    checks: list[CheckResult] = []
    for check in CheckName:
        rules = tuple(result for result in results if result.check is check)
        checks.append(
            CheckResult(
                check=check,
                tier=CHECK_TIERS[check],
                status=combine_statuses(rule.status for rule in rules),
                rules=rules,
            )
        )
    return tuple(checks)


def combine_statuses(statuses: Iterable[ResultStatus]) -> ResultStatus:
    present = set(statuses)
    return next(
        (status for status in STATUS_PRECEDENCE if status in present),
        ResultStatus.SKIPPED,
    )


def decide_verdict(checks: Sequence[CheckResult]) -> Verdict:
    status = combine_statuses(check.status for check in checks)
    if status is ResultStatus.FAILED:
        return Verdict.FAIL
    if status is ResultStatus.OPEN:
        return Verdict.REVIEW
    return Verdict.PASS
