"""Validated refund scenario data and synthetic state."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class RefundModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class RefundToolSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, JsonValue]


class WorldToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: dict[str, JsonValue]
    state_change: dict[str, JsonValue] | None = None
