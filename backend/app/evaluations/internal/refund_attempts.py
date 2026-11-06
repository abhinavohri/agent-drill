from dataclasses import dataclass

from app.evaluations.internal.context import RuleContext
from app.evaluations.internal.trace import ToolAttempt
from app.refunds.facade import CreateRefundArguments, Order, RefundState


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


def refund_attempts(context: RuleContext) -> list[RefundAttempt]:
    return [
        RefundAttempt(attempt, attempt.arguments)
        for attempt in context.trace.attempts
        if isinstance(attempt.arguments, CreateRefundArguments)
    ]


def refunded_order(state: RefundState, payment_id: str) -> Order | None:
    payment = state.payments.get(payment_id)
    return None if payment is None else state.orders.get(payment.order_id)
