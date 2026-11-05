from collections.abc import Sequence
from dataclasses import dataclass

from app.evaluations.internal.models import CheckName, Evidence, ResultStatus, RuleResult
from app.workflows.facade import TeamRole

NO_EVIDENCE = Evidence()


@dataclass(frozen=True)
class RuleIdentity:
    rule_id: str
    owner: TeamRole
    policy: str
    check: CheckName


@dataclass(frozen=True)
class Violation:
    message: str
    event_sequences: tuple[int, ...]
    state_paths: tuple[str, ...] = ()


def rule_result(
    rule: RuleIdentity,
    status: ResultStatus,
    message: str,
    evidence: Evidence = NO_EVIDENCE,
) -> RuleResult:
    return RuleResult(
        rule_id=rule.rule_id,
        check=rule.check,
        owner=rule.owner,
        policy=rule.policy,
        status=status,
        message=message,
        evidence=evidence,
    )


def judge_violations(
    rule: RuleIdentity,
    violations: Sequence[Violation],
    passed_message: str,
) -> RuleResult:
    if not violations:
        return rule_result(rule, ResultStatus.PASSED, passed_message)
    evidence = Evidence(
        event_sequences=tuple(
            sorted({sequence for violation in violations for sequence in violation.event_sequences})
        ),
        state_paths=tuple(
            dict.fromkeys(path for violation in violations for path in violation.state_paths)
        ),
    )
    message = " ".join(violation.message for violation in violations)
    return rule_result(rule, ResultStatus.FAILED, message, evidence)
