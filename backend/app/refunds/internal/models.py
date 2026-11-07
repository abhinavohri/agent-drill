"""Validated refund scenario data and synthetic state."""

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class RefundModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Message(RefundModel):
    role: Literal["customer", "agent"]
    content: str


class Conversation(RefundModel):
    id: str
    customer_id: str
    order_id: str
    messages: list[Message]


class Order(RefundModel):
    id: str
    customer_id: str
    payment_id: str
    total: int = Field(gt=0)
    currency: str
    delivery_status: str


class Payment(RefundModel):
    id: str
    order_id: str
    amount: int = Field(gt=0)
    currency: str
    status: str


class Refund(RefundModel):
    id: str
    payment_id: str
    amount: int = Field(gt=0)
    status: str


class CustomerReply(RefundModel):
    conversation_id: str
    message: str


class HumanEscalation(RefundModel):
    conversation_id: str
    reason: str


class RefundState(RefundModel):
    conversations: dict[str, Conversation]
    orders: dict[str, Order]
    payments: dict[str, Payment]
    refunds: list[Refund] = Field(default_factory=list)
    customer_replies: list[CustomerReply] = Field(default_factory=list)
    human_escalations: list[HumanEscalation] = Field(default_factory=list)


class ToolFault(RefundModel):
    tool: str
    kind: Literal["error", "timeout"]
    times: int = Field(default=1, ge=1)
    message: str


class RefundScenario(RefundModel):
    id: str
    initial_state: RefundState
    faults: list[ToolFault] = Field(default_factory=list)


class RefundScenarioSeed(RefundModel):
    kind: Literal["refund"] = "refund"
    order_total_cents: int = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    delivery_status: str = Field(min_length=1)
    payment_status: str = Field(min_length=1)
    prior_refund_cents: int | None = Field(default=None, gt=0)
    faults: list[ToolFault] = Field(default_factory=list)

    @model_validator(mode="after")
    def refund_does_not_exceed_payment(self) -> Self:
        if self.prior_refund_cents is not None and self.prior_refund_cents > self.order_total_cents:
            raise ValueError("prior_refund_cents cannot exceed order_total_cents")
        return self


@dataclass(frozen=True)
class PreparedRefundScenario:
    conversation_id: str
    scenario: RefundScenario


class ConversationArguments(RefundModel):
    conversation_id: str = Field(alias="conversationId")


class OrderArguments(RefundModel):
    order_id: str = Field(alias="orderId")


class PaymentArguments(RefundModel):
    payment_id: str = Field(alias="paymentId")


class CreateRefundArguments(PaymentArguments):
    amount: int = Field(gt=0)


class SendCustomerReplyArguments(ConversationArguments):
    message: str = Field(min_length=1)


class EscalateToHumanArguments(ConversationArguments):
    reason: str = Field(min_length=1)


class DeliveryStatusResult(RefundModel):
    order_id: str = Field(alias="orderId")
    status: str


class RefundHistoryResult(RefundModel):
    payment_id: str = Field(alias="paymentId")
    refunds: list[Refund]


@dataclass
class PendingFault:
    kind: Literal["error", "timeout"]
    remaining: int
    message: str


class RefundToolSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, JsonValue]
