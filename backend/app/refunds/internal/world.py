"""Stateful synthetic implementation of the refund tools."""

from pydantic import JsonValue

from app.refunds.internal.models import (
    Conversation,
    ConversationArguments,
    CreateRefundArguments,
    CustomerReply,
    DeliveryStatusResult,
    EscalateToHumanArguments,
    HumanEscalation,
    Order,
    OrderArguments,
    Payment,
    PaymentArguments,
    PendingFault,
    Refund,
    RefundHistoryResult,
    RefundScenario,
    SendCustomerReplyArguments,
)


class RefundWorld:
    def __init__(self, scenario: RefundScenario) -> None:
        self._state = scenario.initial_state.model_copy(deep=True)
        self._faults: dict[str, list[PendingFault]] = {}
        for fault in scenario.faults:
            pending = PendingFault(fault.kind, fault.times, fault.message)
            self._faults.setdefault(fault.tool, []).append(pending)

    def snapshot(self) -> dict[str, JsonValue]:
        return self._state.model_dump(mode="json")

    def raise_configured_fault(self, tool_name: str) -> None:
        faults = self._faults.get(tool_name, [])
        fault = next((item for item in faults if item.remaining > 0), None)
        if fault is None:
            return
        fault.remaining -= 1
        if fault.kind == "timeout":
            raise TimeoutError(fault.message)
        raise RuntimeError(fault.message)

    def get_conversation(self, arguments: ConversationArguments) -> Conversation:
        conversation = self._state.conversations.get(arguments.conversation_id)
        if conversation is None:
            raise LookupError(f"Conversation {arguments.conversation_id} does not exist")
        return conversation

    def get_order(self, arguments: OrderArguments) -> Order:
        order = self._state.orders.get(arguments.order_id)
        if order is None:
            raise LookupError(f"Order {arguments.order_id} does not exist")
        return order

    def get_payment(self, arguments: PaymentArguments) -> Payment:
        payment = self._state.payments.get(arguments.payment_id)
        if payment is None:
            raise LookupError(f"Payment {arguments.payment_id} does not exist")
        return payment

    def get_delivery_status(self, arguments: OrderArguments) -> DeliveryStatusResult:
        order = self._state.orders.get(arguments.order_id)
        if order is None:
            raise LookupError(f"Order {arguments.order_id} does not exist")
        return DeliveryStatusResult(order_id=arguments.order_id, status=order.delivery_status)

    def get_refund_history(self, arguments: PaymentArguments) -> RefundHistoryResult:
        refunds = [item for item in self._state.refunds if item.payment_id == arguments.payment_id]
        return RefundHistoryResult(payment_id=arguments.payment_id, refunds=refunds)

    def create_refund(self, arguments: CreateRefundArguments) -> Refund:
        payment = self._state.payments.get(arguments.payment_id)
        if payment is None:
            raise LookupError(f"Payment {arguments.payment_id} does not exist")
        refunded = sum(
            item.amount for item in self._state.refunds if item.payment_id == arguments.payment_id
        )
        if refunded + arguments.amount > payment.amount:
            raise ValueError("Refund amount exceeds the remaining payment amount")
        refund = Refund(
            id=f"refund_{len(self._state.refunds) + 1}",
            payment_id=arguments.payment_id,
            amount=arguments.amount,
            status="succeeded",
        )
        self._state.refunds.append(refund)
        return refund

    def send_customer_reply(self, arguments: SendCustomerReplyArguments) -> CustomerReply:
        if arguments.conversation_id not in self._state.conversations:
            raise LookupError(f"Conversation {arguments.conversation_id} does not exist")
        reply = CustomerReply(
            conversation_id=arguments.conversation_id,
            message=arguments.message,
        )
        self._state.customer_replies.append(reply)
        return reply

    def escalate_to_human(self, arguments: EscalateToHumanArguments) -> HumanEscalation:
        if arguments.conversation_id not in self._state.conversations:
            raise LookupError(f"Conversation {arguments.conversation_id} does not exist")
        escalation = HumanEscalation(
            conversation_id=arguments.conversation_id,
            reason=arguments.reason,
        )
        self._state.human_escalations.append(escalation)
        return escalation
