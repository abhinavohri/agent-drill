"""MCP protocol boundary for the Drill proxy."""

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from pydantic import JsonValue

from app.drill_mcp.internal.proxy import DrillProxyService


def build_server(proxy: DrillProxyService, run_id: str) -> Server:
    server = Server("agent-drill", version="0.1.0")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
                outputSchema=tool.output_schema,
            )
            for tool in proxy.list_tools()
        ]

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        result = await proxy.call_tool(run_id, name, arguments)
        return result.data

    return server


async def run_stdio_server(proxy: DrillProxyService, run_id: str) -> None:
    server = build_server(proxy, run_id)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

