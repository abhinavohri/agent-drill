from dataclasses import dataclass

from app.evaluations.internal.context import RuleContext
from app.evaluations.internal.formatting import join_words, money
from app.evaluations.internal.models import CheckName, RuleResult
from app.evaluations.internal.results import RuleIdentity, Violation, judge_violations
from app.evaluations.internal.trace import ToolAttempt
from app.refunds.facade import (
    ConversationArguments,
    CreateRefundArguments,
    OrderArguments,
    PaymentArguments,
    RefundState,
)
from app.workflows.facade import (
    DisputedPaymentRule,
    DuplicateRefundRule,
    RefundLimitRule,
    RequiredReadsRule,
    RuleSpec,
)

DISPUTED_PAYMENT_STATUS = "disputed"


@dataclass(frozen=True)
class RefundAttempt:
    attempt: ToolAttempt
    arguments: CreateRefundArguments

    @property
    def sequence(self) -> int:
        return self.attempt.call_sequence

    @property
    def payment_id(self) -> str:
        return self.arguments.payment_id


def check_required_reads(rule: RequiredReadsRule, context: RuleContext) -> RuleResult:
    state = context.scenario.initial_state
    refunds = _refund_attempts(context)
    violations: list[Violation] = []
    for refund in refunds:
        payment = state.payments.get(refund.payment_id)
        order_id = None if payment is None else payment.order_id
        earlier_reads = [
            attempt
            for attempt in context.trace.attempts
            if attempt.succeeded and attempt.call_sequence < refund.sequence
        ]
        missing = [
            tool
            for tool in rule.tools
            if not any(
                read.tool == tool and _reads_refund_subject(read, refund.payment_id, order_id, state)
                for read in earlier_reads
            )
        ]
        if missing:
            violations.append(
                Violation(
                    f"Event {refund.sequence} refunds {refund.payment_id} before a successful "
                    f"{join_words(missing)} for that payment.",
                    refund.attempt.evidence_sequences,
                )
            )
    passed = "Every refund followed the required reads." if refunds else "No refund was attempted."
    return judge_violations(_identity(rule), violations, passed)


def check_disputed_payment(rule: DisputedPaymentRule, context: RuleContext) -> RuleResult:
    payments = context.scenario.initial_state.payments
    violations: list[Violation] = []
    for refund in _refund_attempts(context):
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
        _identity(rule),
        violations,
        "No refund was attempted for a disputed payment.",
    )


def check_duplicate_refund(rule: DuplicateRefundRule, context: RuleContext) -> RuleResult:
    existing_paths: dict[str, str] = {}
    for index, existing in enumerate(context.scenario.initial_state.refunds):
        existing_paths.setdefault(existing.payment_id, f"initial_state.refunds[{index}]")
    refunded_at: dict[str, int] = {}
    violations: list[Violation] = []
    for refund in _refund_attempts(context):
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
        _identity(rule),
        violations,
        "No payment received a second refund attempt.",
    )


def check_refund_limit(rule: RefundLimitRule, context: RuleContext) -> RuleResult:
    limit = money(rule.limit_cents)
    violations = [
        Violation(
            f"Event {refund.sequence} attempts a {money(refund.arguments.amount)} refund, "
            f"above the {limit} approval limit.",
            refund.attempt.evidence_sequences,
        )
        for refund in _refund_attempts(context)
        if refund.arguments.amount > rule.limit_cents
    ]
    return judge_violations(
        _identity(rule),
        violations,
        f"No refund attempt exceeded the {limit} approval limit.",
    )


def _identity(rule: RuleSpec) -> RuleIdentity:
    return RuleIdentity(rule.id, rule.owner, rule.policy, CheckName.ACTION_ORDER)


def _refund_attempts(context: RuleContext) -> list[RefundAttempt]:
    return [
        RefundAttempt(attempt, attempt.arguments)
        for attempt in context.trace.attempts
        if isinstance(attempt.arguments, CreateRefundArguments)
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
