from typing import assert_never

from app.evaluations.internal.baseline_rules import (
    check_declared_tools,
    check_expected_outcome,
    check_run_completed,
    check_valid_arguments,
)
from app.evaluations.internal.context import RuleContext, build_context
from app.evaluations.internal.models import (
    RecordedRun,
    ResultStatus,
    ReviewInput,
    RuleResult,
    RunResult,
    Verdict,
)
from app.evaluations.internal.refund_rules import (
    check_disputed_payment,
    check_duplicate_refund,
    check_refund_limit,
    check_required_reads,
)
from app.evaluations.internal.review_rules import (
    pending_roles,
    review_customer_reply,
    review_release,
)
from app.evaluations.internal.verdict import decide_verdict, group_checks
from app.workflows.facade import (
    CustomerReplyReview,
    DisputedPaymentRule,
    DuplicateRefundRule,
    PolicyRule,
    RefundLimitRule,
    ReleaseApprovalReview,
    RequiredReadsRule,
    ReviewRule,
    Scenario,
    TeamRole,
    WorkflowSpec,
)


def evaluate_run(
    workflow: WorkflowSpec,
    scenario: Scenario,
    recorded: RecordedRun,
    review: ReviewInput,
) -> RunResult:
    context = build_context(workflow, scenario, recorded)
    hard_results = _evaluate_hard_rules(context)
    review_results = tuple(_evaluate_review_rule(rule, context, review) for rule in workflow.reviews)
    checks = group_checks((*hard_results, *review_results))
    verdict = decide_verdict(checks)
    return RunResult(
        run_id=recorded.run.id,
        agent_id=recorded.agent_id,
        agent_version=recorded.agent_version,
        workflow_id=workflow.id,
        scenario_id=scenario.id,
        verdict=verdict,
        outcome=context.outcome,
        expected_outcomes=scenario.expected_outcomes,
        pending_approvals=() if verdict is Verdict.FAIL else _pending_approvals(workflow, review),
        checks=checks,
        actions=context.trace.actions,
    )


def _evaluate_hard_rules(context: RuleContext) -> tuple[RuleResult, ...]:
    results = (
        check_valid_arguments(context),
        check_declared_tools(context),
        *(_evaluate_policy_rule(rule, context) for rule in context.workflow.rules),
        check_run_completed(context),
        check_expected_outcome(context),
    )
    assert all(result.status is not ResultStatus.OPEN for result in results)
    return results


def _evaluate_policy_rule(rule: PolicyRule, context: RuleContext) -> RuleResult:
    match rule:
        case RequiredReadsRule():
            return check_required_reads(rule, context)
        case DisputedPaymentRule():
            return check_disputed_payment(rule, context)
        case DuplicateRefundRule():
            return check_duplicate_refund(rule, context)
        case RefundLimitRule():
            return check_refund_limit(rule, context)
        case _:
            assert_never(rule)


def _evaluate_review_rule(rule: ReviewRule, context: RuleContext, review: ReviewInput) -> RuleResult:
    match rule:
        case CustomerReplyReview():
            return review_customer_reply(rule, context, review)
        case ReleaseApprovalReview():
            return review_release(rule, review)
        case _:
            assert_never(rule)


def _pending_approvals(workflow: WorkflowSpec, review: ReviewInput) -> tuple[TeamRole, ...]:
    roles = (
        role
        for rule in workflow.reviews
        if isinstance(rule, ReleaseApprovalReview)
        for role in pending_roles(rule, review)
    )
    return tuple(dict.fromkeys(roles))
