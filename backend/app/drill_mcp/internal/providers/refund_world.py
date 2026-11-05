"""Adapt the refund feature to the Drill MCP provider contract."""

from pydantic import JsonValue

from app.drill_mcp.internal.models import ToolDefinition, ToolResult
from app.refunds.facade import RefundWorld


class RefundWorldToolClient:
    def __init__(self, world: RefundWorld) -> None:
        self._world = world

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        return tuple(
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
            for tool in self._world.list_tools()
        )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> ToolResult:
        result = await self._world.call_tool(tool_name, arguments)
        return ToolResult(data=result.data, state_change=result.state_change)

    def snapshot(self) -> dict[str, JsonValue]:
        return self._world.snapshot()

    async def close(self) -> None:
        return None
