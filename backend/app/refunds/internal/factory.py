"""Build a synthetic refund world from declarative starting conditions."""

from app.refunds.internal.models import (
    Conversation,
    Order,
    Payment,
    PreparedRefundScenario,
    Refund,
    RefundScenario,
    RefundScenarioSeed,
    RefundState,
)


def prepare_refund_scenario(
    scenario_id: str,
    seed: RefundScenarioSeed,
) -> PreparedRefundScenario:
    customer_id = f"customer-{scenario_id}"
    conversation_id = f"conversation-{scenario_id}"
    order_id = f"order-{scenario_id}"
    payment_id = f"payment-{scenario_id}"
    refunds = (
        [
            Refund(
                id=f"refund-{scenario_id}",
                payment_id=payment_id,
                amount=seed.prior_refund_cents,
                status="completed",
            )
        ]
        if seed.prior_refund_cents is not None
        else []
    )
    state = RefundState(
        conversations={
            conversation_id: Conversation(
                id=conversation_id,
                customer_id=customer_id,
                order_id=order_id,
                messages=[],
            )
        },
        orders={
            order_id: Order(
                id=order_id,
                customer_id=customer_id,
                payment_id=payment_id,
                total=seed.order_total_cents,
                currency=seed.currency,
                delivery_status=seed.delivery_status,
            )
        },
        payments={
            payment_id: Payment(
                id=payment_id,
                order_id=order_id,
                amount=seed.order_total_cents,
                currency=seed.currency,
                status=seed.payment_status,
            )
        },
        refunds=refunds,
    )
    return PreparedRefundScenario(
        conversation_id=conversation_id,
        scenario=RefundScenario(
            id=scenario_id,
            initial_state=state,
            faults=list(seed.faults),
        ),
    )
