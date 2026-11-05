"""Expose the synthetic refund world through the generic tool-provider contract."""

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


class RefundToolProvider:
    def __init__(self, world: RefundWorld) -> None:
        self._world = world

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
        self._world.raise_configured_fault(tool_name)

        if tool_name == "get_conversation":
            result = self._world.get_conversation(ConversationArguments.model_validate(arguments))
            return self._read_result(result)
        if tool_name == "get_order":
            result = self._world.get_order(OrderArguments.model_validate(arguments))
            return self._read_result(result)
        if tool_name == "get_payment":
            result = self._world.get_payment(PaymentArguments.model_validate(arguments))
            return self._read_result(result)
        if tool_name == "get_delivery_status":
            result = self._world.get_delivery_status(OrderArguments.model_validate(arguments))
            return self._read_result(result)
        if tool_name == "get_refund_history":
            result = self._world.get_refund_history(PaymentArguments.model_validate(arguments))
            return self._read_result(result)
        if tool_name == "create_refund":
            result = self._world.create_refund(CreateRefundArguments.model_validate(arguments))
            return self._write_result("refund", result)
        if tool_name == "send_customer_reply":
            parsed = SendCustomerReplyArguments.model_validate(arguments)
            return self._write_result("customer_reply", self._world.send_customer_reply(parsed))
        if tool_name == "escalate_to_human":
            parsed = EscalateToHumanArguments.model_validate(arguments)
            return self._write_result("human_escalation", self._world.escalate_to_human(parsed))
        raise LookupError(f"Unknown refund tool: {tool_name}")

    def snapshot(self) -> dict[str, JsonValue]:
        return self._world.snapshot()

    async def close(self) -> None:
        return None

    @staticmethod
    def _read_result(result: BaseModel) -> ToolResult:
        return ToolResult(data=result.model_dump(mode="json", by_alias=True))

    @staticmethod
    def _write_result(resource: str, result: BaseModel) -> ToolResult:
        data = result.model_dump(mode="json", by_alias=True)
        change = StateChange(resource=resource, operation="created", value=data)
        return ToolResult(data=data, state_change=change)
