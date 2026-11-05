"""Mock upstream MCP provider for local backend development."""

import asyncio

from pydantic import JsonValue

from app.drill_mcp.internal.models import ToolDefinition, ToolResult


class MockUpstreamToolClient:
    def __init__(self, delay_seconds: float = 0) -> None:
        self._delay_seconds = delay_seconds
        self.closed = False
        self.calls: list[tuple[str, dict[str, JsonValue]]] = []
        self._tools = (
            ToolDefinition(
                name="get_payment",
                description="Read a payment from the target tool server.",
                input_schema={
                    "type": "object",
                    "properties": {"paymentId": {"type": "string"}},
                    "required": ["paymentId"],
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                name="create_refund",
                description="Create a refund through the target tool server.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "paymentId": {"type": "string"},
                        "amount": {"type": "integer", "minimum": 1},
                    },
                    "required": ["paymentId", "amount"],
                    "additionalProperties": False,
                },
            ),
        )

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return self._tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> ToolResult:
        if self._delay_seconds:
            await asyncio.sleep(self._delay_seconds)
        if tool_name not in {tool.name for tool in self._tools}:
            raise LookupError(f"Unknown upstream tool: {tool_name}")

        self.calls.append((tool_name, arguments))
        return ToolResult(data={"provider": "mock", "tool": tool_name, "arguments": arguments})

    async def close(self) -> None:
        self.closed = True

