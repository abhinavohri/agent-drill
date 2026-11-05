"""Tool contracts for the synthetic refund world."""

from app.refunds.internal.models import RefundToolSpec


def _object_schema(properties: dict[str, object], required: list[str]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


REFUND_TOOL_SPECS = (
    RefundToolSpec(
        name="get_conversation",
        description="Read a customer conversation.",
        input_schema=_object_schema({"conversationId": {"type": "string"}}, ["conversationId"]),
    ),
    RefundToolSpec(
        name="get_order",
        description="Read an order.",
        input_schema=_object_schema({"orderId": {"type": "string"}}, ["orderId"]),
    ),
    RefundToolSpec(
        name="get_payment",
        description="Read a payment.",
        input_schema=_object_schema({"paymentId": {"type": "string"}}, ["paymentId"]),
    ),
    RefundToolSpec(
        name="get_delivery_status",
        description="Read the delivery status for an order.",
        input_schema=_object_schema({"orderId": {"type": "string"}}, ["orderId"]),
    ),
    RefundToolSpec(
        name="get_refund_history",
        description="Read the refunds for a payment.",
        input_schema=_object_schema({"paymentId": {"type": "string"}}, ["paymentId"]),
    ),
    RefundToolSpec(
        name="create_refund",
        description="Create a refund for a payment.",
        input_schema=_object_schema(
            {
                "paymentId": {"type": "string"},
                "amount": {"type": "integer", "minimum": 1},
            },
            ["paymentId", "amount"],
        ),
    ),
    RefundToolSpec(
        name="send_customer_reply",
        description="Send a reply to the customer conversation.",
        input_schema=_object_schema(
            {"conversationId": {"type": "string"}, "message": {"type": "string", "minLength": 1}},
            ["conversationId", "message"],
        ),
    ),
    RefundToolSpec(
        name="escalate_to_human",
        description="Escalate a customer conversation to a human reviewer.",
        input_schema=_object_schema(
            {"conversationId": {"type": "string"}, "reason": {"type": "string", "minLength": 1}},
            ["conversationId", "reason"],
        ),
    ),
)
