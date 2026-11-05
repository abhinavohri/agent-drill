"""Expose the synthetic refund world through the generic tool-provider contract."""

from collections.abc import Callable

from pydantic import BaseModel, JsonValue

from app.drill_mcp.facade import ToolDefinition, ToolResult
from app.refunds.internal.models import (
    ConversationArguments,
    CreateRefundArguments,
    EscalateToHumanArguments,
    OrderArguments,
    PaymentArguments,
    SendCustomerReplyArguments,
)
from app.refunds.internal.tool_catalog import REFUND_TOOL_SPECS
from app.refunds.internal.world import RefundWorld
from app.simulations.facade import StateChange

ToolHandler = Callable[[dict[str, JsonValue]], ToolResult]


class RefundToolProvider:
    def __init__(self, world: RefundWorld) -> None:
        self._world = world
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
        assert set(self._handlers) == {tool.name for tool in REFUND_TOOL_SPECS}

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return tuple(
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
            for tool in REFUND_TOOL_SPECS
        )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> ToolResult:
        try:
            handler = self._handlers[tool_name]
        except KeyError as exc:
            raise LookupError(f"Unknown refund tool: {tool_name}") from exc
        self._world.raise_configured_fault(tool_name)
        return handler(arguments)

    def snapshot(self) -> dict[str, JsonValue]:
        return self._world.snapshot()

    async def close(self) -> None:
        return None

    def _get_conversation(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = ConversationArguments.model_validate(arguments)
        return self._read_result(self._world.get_conversation(parsed))

    def _get_order(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = OrderArguments.model_validate(arguments)
        return self._read_result(self._world.get_order(parsed))

    def _get_payment(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = PaymentArguments.model_validate(arguments)
        return self._read_result(self._world.get_payment(parsed))

    def _get_delivery_status(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = OrderArguments.model_validate(arguments)
        return self._read_result(self._world.get_delivery_status(parsed))

    def _get_refund_history(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = PaymentArguments.model_validate(arguments)
        return self._read_result(self._world.get_refund_history(parsed))

    def _create_refund(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = CreateRefundArguments.model_validate(arguments)
        return self._write_result("refund", self._world.create_refund(parsed))

    def _send_customer_reply(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = SendCustomerReplyArguments.model_validate(arguments)
        return self._write_result("customer_reply", self._world.send_customer_reply(parsed))

    def _escalate_to_human(self, arguments: dict[str, JsonValue]) -> ToolResult:
        parsed = EscalateToHumanArguments.model_validate(arguments)
        return self._write_result("human_escalation", self._world.escalate_to_human(parsed))

    @staticmethod
    def _read_result(result: BaseModel) -> ToolResult:
        return ToolResult(data=result.model_dump(mode="json", by_alias=True))

    @staticmethod
    def _write_result(resource: str, result: BaseModel) -> ToolResult:
        data = result.model_dump(mode="json", by_alias=True)
        change = StateChange(resource=resource, operation="created", value=data)
        return ToolResult(data=data, state_change=change)
