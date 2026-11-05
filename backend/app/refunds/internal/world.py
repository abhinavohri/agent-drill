"""Stateful synthetic implementation of the refund tools."""

from collections.abc import Callable

from pydantic import JsonValue

from app.refunds.internal.models import (
    CustomerReply,
    HumanEscalation,
    Refund,
    RefundScenario,
    RefundToolSpec,
    WorldToolResult,
)
from app.refunds.internal.tool_catalog import REFUND_TOOL_SPECS

ToolHandler = Callable[[dict[str, JsonValue]], WorldToolResult]


class RefundWorld:
    def __init__(self, scenario: RefundScenario) -> None:
        self._state = scenario.initial_state.model_copy(deep=True)
        self._faults = {fault.tool: [fault.kind, fault.times, fault.message] for fault in scenario.faults}
        self._handlers: dict[str, ToolHandler] = {
            "get_conversation": self._get_conversation,
            "get_order": self._get_order,
            "get_payment": self._get_payment,
            "get_delivery_status": self._get_delivery_status,
            "get_refund_history": self._get_refund_history,
            "create_refund": self._create_refund,
            "send_customer_reply": self._send_customer_reply,
            "escalate_to_human": self._escalate_to_human,
        }

    def list_tools(self) -> tuple[RefundToolSpec, ...]:
        return REFUND_TOOL_SPECS

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> WorldToolResult:
        self._raise_configured_fault(tool_name)
        try:
            handler = self._handlers[tool_name]
        except KeyError as exc:
            raise LookupError(f"Unknown refund tool: {tool_name}") from exc
        return handler(arguments)

    def snapshot(self) -> dict[str, JsonValue]:
        return self._state.model_dump(mode="json")

    def _raise_configured_fault(self, tool_name: str) -> None:
        fault = self._faults.get(tool_name)
        if fault is None or int(fault[1]) < 1:
            return
        fault[1] = int(fault[1]) - 1
        message = str(fault[2])
        if fault[0] == "timeout":
            raise TimeoutError(message)
        raise RuntimeError(message)

    def _get_conversation(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        conversation_id = str(arguments["conversationId"])
        conversation = self._state.conversations.get(conversation_id)
        if conversation is None:
            raise LookupError(f"Conversation {conversation_id} does not exist")
        return WorldToolResult(data=conversation.model_dump(mode="json"))

    def _get_order(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        order_id = str(arguments["orderId"])
        order = self._state.orders.get(order_id)
        if order is None:
            raise LookupError(f"Order {order_id} does not exist")
        return WorldToolResult(data=order.model_dump(mode="json"))

    def _get_payment(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        payment_id = str(arguments["paymentId"])
        payment = self._state.payments.get(payment_id)
        if payment is None:
            raise LookupError(f"Payment {payment_id} does not exist")
        return WorldToolResult(data=payment.model_dump(mode="json"))

    def _get_delivery_status(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        order_id = str(arguments["orderId"])
        order = self._state.orders.get(order_id)
        if order is None:
            raise LookupError(f"Order {order_id} does not exist")
        return WorldToolResult(data={"orderId": order_id, "status": order.delivery_status})

    def _get_refund_history(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        payment_id = str(arguments["paymentId"])
        refunds = [
            refund.model_dump(mode="json")
            for refund in self._state.refunds
            if refund.payment_id == payment_id
        ]
        return WorldToolResult(data={"paymentId": payment_id, "refunds": refunds})

    def _create_refund(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        payment_id = str(arguments["paymentId"])
        amount = int(arguments["amount"])
        payment = self._state.payments.get(payment_id)
        if payment is None:
            raise LookupError(f"Payment {payment_id} does not exist")
        refunded = sum(item.amount for item in self._state.refunds if item.payment_id == payment_id)
        if refunded + amount > payment.amount:
            raise ValueError("Refund amount exceeds the remaining payment amount")
        refund = Refund(
            id=f"refund_{len(self._state.refunds) + 1}",
            payment_id=payment_id,
            amount=amount,
            status="succeeded",
        )
        self._state.refunds.append(refund)
        data = refund.model_dump(mode="json")
        return WorldToolResult(
            data=data,
            state_change={"resource": "refund", "operation": "created", "value": data},
        )

    def _send_customer_reply(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        conversation_id = str(arguments["conversationId"])
        if conversation_id not in self._state.conversations:
            raise LookupError(f"Conversation {conversation_id} does not exist")
        reply = CustomerReply(conversation_id=conversation_id, message=str(arguments["message"]))
        self._state.customer_replies.append(reply)
        data = reply.model_dump(mode="json")
        return WorldToolResult(
            data=data,
            state_change={"resource": "customer_reply", "operation": "created", "value": data},
        )

    def _escalate_to_human(self, arguments: dict[str, JsonValue]) -> WorldToolResult:
        conversation_id = str(arguments["conversationId"])
        if conversation_id not in self._state.conversations:
            raise LookupError(f"Conversation {conversation_id} does not exist")
        escalation = HumanEscalation(
            conversation_id=conversation_id,
            reason=str(arguments["reason"]),
        )
        self._state.human_escalations.append(escalation)
        data = escalation.model_dump(mode="json")
        return WorldToolResult(
            data=data,
            state_change={"resource": "human_escalation", "operation": "created", "value": data},
        )
