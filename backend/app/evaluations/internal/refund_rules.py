from collections.abc import Sequence

from app.evaluations.internal.context import RuleContext
from app.evaluations.internal.formatting import join_words, money
from app.evaluations.internal.models import RuleResult
from app.evaluations.internal.refund_attempts import RefundAttempt, refund_attempts
from app.evaluations.internal.results import Violation, judge_violations, policy_identity
from app.evaluations.internal.trace import ToolAttempt
from app.refunds.facade import (
    ConversationArguments,
    OrderArguments,
    PaymentArguments,
    RefundState,
)
from app.workflows.facade import (
    DisputedPaymentRule,
    DuplicateRefundRule,
    RefundLimitRule,
    RefundRetryRule,
    RequiredReadsRule,
)

DISPUTED_PAYMENT_STATUS = "disputed"
RUN_START = 0


def check_required_reads(rule: RequiredReadsRule, context: RuleContext) -> RuleResult:
    refunds = refund_attempts(context)
    violations: list[Violation] = []
    for refund in refunds:
        missing = _missing_reads(context, rule.tools, refund, after=RUN_START)
        if missing:
            violations.append(
                Violation(
                    f"Event {refund.sequence} refunds {refund.payment_id} before a successful "
                    f"{join_words(missing)} for that payment.",
                    refund.attempt.evidence_sequences,
                )
            )
    passed = "Every refund followed the required reads." if refunds else "No refund was attempted."
    return judge_violations(policy_identity(rule), violations, passed)


def check_disputed_payment(rule: DisputedPaymentRule, context: RuleContext) -> RuleResult:
    payments = context.scenario.initial_state.payments
    violations: list[Violation] = []
    for refund in refund_attempts(context):
        payment = payments.get(refund.payment_id)
        if payment is None or payment.status != DISPUTED_PAYMENT_STATUS:
            continue
        violations.append(
            Violation(
                f"Event {refund.sequence} attempts a {money(refund.arguments.amount)} refund "
                f"for disputed payment {refund.payment_id}.",
                refund.attempt.evidence_sequences,
                (
                    f"initial_state.payments.{refund.payment_id}.status",
                    *_created_refund_paths(context, refund.payment_id),
                ),
            )
        )
    return judge_violations(
        policy_identity(rule),
        violations,
        "No refund was attempted for a disputed payment.",
    )


def check_duplicate_refund(rule: DuplicateRefundRule, context: RuleContext) -> RuleResult:
    existing_paths: dict[str, str] = {}
    for index, existing in enumerate(context.scenario.initial_state.refunds):
        existing_paths.setdefault(existing.payment_id, f"initial_state.refunds[{index}]")
    refunded_at: dict[str, int] = {}
    violations: list[Violation] = []
    for refund in refund_attempts(context):
        message = (
            f"Event {refund.sequence} attempts another refund for {refund.payment_id}, "
            "which already has a refund."
        )
        if refund.payment_id in existing_paths:
            violations.append(
                Violation(
                    message,
                    refund.attempt.evidence_sequences,
                    (existing_paths[refund.payment_id],),
                )
            )
        elif refund.payment_id in refunded_at:
            violations.append(
                Violation(
                    message,
                    (refunded_at[refund.payment_id], *refund.attempt.evidence_sequences),
                )
            )
        if refund.attempt.succeeded:
            refunded_at.setdefault(refund.payment_id, refund.sequence)
    return judge_violations(
        policy_identity(rule),
        violations,
        "No payment received a second refund attempt.",
    )


def check_refund_limit(rule: RefundLimitRule, context: RuleContext) -> RuleResult:
    limit = money(rule.limit_cents)
    refunded: dict[str, int] = {}
    violations: list[Violation] = []
    for refund in refund_attempts(context):
        earlier = refunded.get(refund.payment_id, 0)
        total = earlier + refund.arguments.amount
        if total > rule.limit_cents:
            violations.append(
                Violation(
                    _limit_message(refund, earlier, total, limit),
                    refund.attempt.evidence_sequences,
                )
            )
        if refund.attempt.succeeded:
            refunded[refund.payment_id] = total
    return judge_violations(
        policy_identity(rule),
        violations,
        f"Refunds stayed within the {limit} approval limit for every payment.",
    )


def _limit_message(refund: RefundAttempt, earlier: int, total: int, limit: str) -> str:
    amount = money(refund.arguments.amount)
    if earlier == 0:
        return f"Event {refund.sequence} attempts a {amount} refund, above the {limit} approval limit."
    return (
        f"Event {refund.sequence} attempts a {amount} refund that brings {refund.payment_id} "
        f"to {money(total)}, above the {limit} approval limit."
    )


def check_refund_retry(rule: RefundRetryRule, context: RuleContext) -> RuleResult:
    failed_at: dict[str, int] = {}
    retried = False
    violations: list[Violation] = []
    for refund in refund_attempts(context):
        failure = failed_at.get(refund.payment_id)
        if failure is not None:
            retried = True
            missing = _missing_reads(context, rule.tools, refund, after=failure)
            if missing:
                violations.append(
                    Violation(
                        f"Event {refund.sequence} retries the refund for {refund.payment_id} "
                        f"without a new {join_words(missing)} after the failed attempt at "
                        f"event {failure}.",
                        refund.attempt.evidence_sequences,
                    )
                )
        if refund.attempt.succeeded:
            failed_at.pop(refund.payment_id, None)
        else:
            failed_at[refund.payment_id] = refund.sequence
    passed = (
        f"Every retried refund followed a new {join_words(rule.tools)}."
        if retried
        else "No failed refund was retried."
    )
    return judge_violations(policy_identity(rule), violations, passed)


def _missing_reads(
    context: RuleContext,
    tools: Sequence[str],
    refund: RefundAttempt,
    *,
    after: int,
) -> list[str]:
    state = context.scenario.initial_state
    payment = state.payments.get(refund.payment_id)
    order_id = None if payment is None else payment.order_id
    reads = [
        attempt
        for attempt in context.trace.attempts
        if attempt.succeeded and after < attempt.call_sequence < refund.sequence
    ]
    return [
        tool
        for tool in tools
        if not any(
            read.tool == tool and _reads_refund_subject(read, refund.payment_id, order_id, state)
            for read in reads
        )
    ]


def _reads_refund_subject(
    attempt: ToolAttempt,
    payment_id: str,
    order_id: str | None,
    state: RefundState,
) -> bool:
    match attempt.arguments:
        case PaymentArguments(payment_id=read_payment_id):
            return read_payment_id == payment_id
        case OrderArguments(order_id=read_order_id):
            return read_order_id == order_id
        case ConversationArguments(conversation_id=conversation_id):
            conversation = state.conversations.get(conversation_id)
            return conversation is not None and conversation.order_id == order_id
    return False


def _created_refund_paths(context: RuleContext, payment_id: str) -> tuple[str, ...]:
    if context.final_state is None:
        return ()
    initial_ids = {refund.id for refund in context.scenario.initial_state.refunds}
    return tuple(
        f"final_state.refunds[{index}]"
        for index, refund in enumerate(context.final_state.refunds)
        if refund.id not in initial_ids and refund.payment_id == payment_id
    )
