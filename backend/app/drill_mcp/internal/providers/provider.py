"""Contract for a tool provider connected to the Drill MCP server."""

from typing import Protocol

from pydantic import JsonValue

from app.drill_mcp.internal.models import ToolDefinition, ToolResult


class ToolProvider(Protocol):
    async def list_tools(self) -> tuple[ToolDefinition, ...]: ...

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> ToolResult: ...

    async def close(self) -> None: ...
