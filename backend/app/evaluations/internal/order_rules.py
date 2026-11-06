from app.evaluations.internal.context import RuleContext
from app.evaluations.internal.models import RuleResult
from app.evaluations.internal.refund_attempts import refund_attempts, refunded_order
from app.evaluations.internal.results import Violation, judge_violations, policy_identity
from app.workflows.facade import CustomerOrderRule, DeliveredOrderRule

DELIVERED_STATUS = "delivered"


def check_customer_order(rule: CustomerOrderRule, context: RuleContext) -> RuleResult:
    scenario = context.scenario
    state = scenario.initial_state
    customer_id = state.conversations[scenario.conversation_id].customer_id
    violations: list[Violation] = []
    for refund in refund_attempts(context):
        order = refunded_order(state, refund.payment_id)
        if order is None or order.customer_id == customer_id:
            continue
        violations.append(
            Violation(
                f"Event {refund.sequence} refunds {refund.payment_id} for order {order.id}, "
                f"which belongs to {order.customer_id}, not to {customer_id}.",
                refund.attempt.evidence_sequences,
                (
                    f"initial_state.orders.{order.id}.customer_id",
                    f"initial_state.conversations.{scenario.conversation_id}.customer_id",
                ),
            )
        )
    return judge_violations(
        policy_identity(rule),
        violations,
        "Every refund attempt was for the conversation customer's own order.",
    )


def check_delivered_order(rule: DeliveredOrderRule, context: RuleContext) -> RuleResult:
    state = context.scenario.initial_state
    violations: list[Violation] = []
    for refund in refund_attempts(context):
        order = refunded_order(state, refund.payment_id)
        if order is None or order.delivery_status == DELIVERED_STATUS:
            continue
        violations.append(
            Violation(
                f"Event {refund.sequence} refunds order {order.id}, which is "
                f"{order.delivery_status.replace('_', ' ')}, not delivered.",
                refund.attempt.evidence_sequences,
                (f"initial_state.orders.{order.id}.delivery_status",),
            )
        )
    return judge_violations(
        policy_identity(rule),
        violations,
        "Every refund attempt was for a delivered order.",
    )
