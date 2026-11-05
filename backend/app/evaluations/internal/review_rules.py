from app.evaluations.internal.context import RuleContext, new_item_paths
from app.evaluations.internal.formatting import join_words
from app.evaluations.internal.models import (
    CheckName,
    Decision,
    Evidence,
    ResultStatus,
    ReviewDecision,
    ReviewInput,
    RuleResult,
)
from app.evaluations.internal.results import RuleIdentity, rule_result
from app.refunds.facade import SendCustomerReplyArguments
from app.workflows.facade import CustomerReplyReview, ReleaseApprovalReview, TeamRole


def review_customer_reply(
    rule: CustomerReplyReview,
    context: RuleContext,
    review: ReviewInput,
) -> RuleResult:
    identity = RuleIdentity(rule.id, rule.owner, rule.policy, CheckName.SEMANTIC_OUTPUT)
    evidence = _reply_evidence(context)
    blocks = _decisions(review, Decision.BLOCK)
    if blocks:
        return rule_result(identity, ResultStatus.FAILED, f"Blocked by {_reviewers(blocks)}.", evidence)
    approvals = _decisions(review, Decision.APPROVE)
    if approvals:
        message = f"Accepted by {_reviewers(approvals)}."
        return rule_result(identity, ResultStatus.PASSED, message, evidence)
    concerns = [item for item in review.judge_assessments if not item.acceptable]
    if concerns:
        notes = "; ".join(f"{item.judge}: {item.note}" for item in concerns)
        message = f"A judge raised a concern ({notes}). A reviewer must decide."
        return rule_result(identity, ResultStatus.OPEN, message, evidence)
    if review.judge_assessments:
        judges = join_words(item.judge for item in review.judge_assessments)
        message = f"{judges} found the reply acceptable."
        return rule_result(identity, ResultStatus.PASSED, message, evidence)
    if not evidence.event_sequences:
        message = "The agent sent no customer reply. A reviewer must decide."
        return rule_result(identity, ResultStatus.OPEN, message, evidence)
    message = "Waiting for a reviewer to check the customer reply."
    return rule_result(identity, ResultStatus.OPEN, message, evidence)


def review_release(rule: ReleaseApprovalReview, review: ReviewInput) -> RuleResult:
    identity = RuleIdentity(rule.id, rule.owner, rule.policy, CheckName.HUMAN_APPROVAL)
    blocks = _decisions(review, Decision.BLOCK)
    if blocks:
        return rule_result(identity, ResultStatus.FAILED, f"Release blocked by {_reviewers(blocks)}.")
    pending = pending_roles(rule, review)
    if pending:
        message = f"Waiting for approval from {join_words(pending)}."
        return rule_result(identity, ResultStatus.OPEN, message)
    approvals = [item for item in _decisions(review, Decision.APPROVE) if item.role in rule.roles]
    return rule_result(identity, ResultStatus.PASSED, f"Approved by {_reviewers(approvals)}.")


def pending_roles(rule: ReleaseApprovalReview, review: ReviewInput) -> tuple[TeamRole, ...]:
    approved = {item.role for item in _decisions(review, Decision.APPROVE)}
    return tuple(role for role in rule.roles if role not in approved)


def _reply_evidence(context: RuleContext) -> Evidence:
    sequences = tuple(
        attempt.call_sequence
        for attempt in context.trace.attempts
        if attempt.succeeded and isinstance(attempt.arguments, SendCustomerReplyArguments)
    )
    if context.final_state is None:
        return Evidence(event_sequences=sequences)
    paths = new_item_paths(
        "customer_replies",
        len(context.scenario.initial_state.customer_replies),
        len(context.final_state.customer_replies),
    )
    return Evidence(event_sequences=sequences, state_paths=paths)


def _decisions(review: ReviewInput, decision: Decision) -> list[ReviewDecision]:
    return [item for item in review.decisions if item.decision is decision]


def _reviewers(decisions: list[ReviewDecision]) -> str:
    return join_words(f"{item.reviewer} ({item.role})" for item in decisions)
