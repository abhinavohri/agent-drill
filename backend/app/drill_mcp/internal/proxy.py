"""MCP tool discovery, validation, forwarding, and event recording."""

import asyncio

import jsonschema
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import JsonValue

from app.drill_mcp.internal.models import ToolDefinition, ToolResult
from app.drill_mcp.internal.providers.upstream import UpstreamToolClient
from app.simulations.facade import ActionLimitExceededError, SimulationService


class ToolNotAllowedError(PermissionError):
    pass


class InvalidToolArgumentsError(ValueError):
    pass


class UpstreamToolTimeoutError(TimeoutError):
    pass


class UpstreamToolError(RuntimeError):
    pass


class DrillProxyService:
    def __init__(
        self,
        upstream: UpstreamToolClient,
        simulations: SimulationService,
        *,
        allowed_tools: set[str] | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self._upstream = upstream
        self._simulations = simulations
        self._allowed_tools = allowed_tools
        self._timeout_seconds = timeout_seconds
        self._tools: dict[str, ToolDefinition] = {}

    async def initialize(self) -> None:
        tools = await self._upstream.list_tools()
        self._tools = {tool.name: tool for tool in tools}

    def list_tools(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())

    async def call_tool(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> ToolResult:
        tool = self._get_allowed_tool(tool_name)
        self._validate_arguments(tool, arguments)
        try:
            self._simulations.record_tool_call(run_id, tool_name, arguments)
        except ActionLimitExceededError as exc:
            await self._simulations.fail_run(run_id, str(exc))
            raise

        try:
            async with asyncio.timeout(self._timeout_seconds):
                result = await self._upstream.call_tool(tool_name, arguments)
        except TimeoutError as exc:
            message = f"Tool {tool_name} exceeded the {self._timeout_seconds:g} second timeout"
            self._simulations.record_tool_error(run_id, tool_name, message)
            raise UpstreamToolTimeoutError(message) from exc
        except Exception as exc:
            message = f"Upstream tool {tool_name} failed: {exc}"
            self._simulations.record_tool_error(run_id, tool_name, message)
            raise UpstreamToolError(message) from exc

        self._simulations.record_tool_result(run_id, tool_name, result.data)
        if result.state_change is not None:
            self._simulations.record_state_change(run_id, tool_name, result.state_change)
        return result

    async def close(self) -> None:
        await self._upstream.close()

    def _get_allowed_tool(self, tool_name: str) -> ToolDefinition:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ToolNotAllowedError(f"Tool {tool_name} is not exposed by the upstream server")
        if self._allowed_tools is not None and tool_name not in self._allowed_tools:
            raise ToolNotAllowedError(f"Tool {tool_name} is not allowed for this run")
        return tool

    @staticmethod
    def _validate_arguments(
        tool: ToolDefinition,
        arguments: dict[str, JsonValue],
    ) -> None:
        try:
            jsonschema.validate(arguments, tool.input_schema)
        except (SchemaError, ValidationError) as exc:
            raise InvalidToolArgumentsError(
                f"Invalid arguments for {tool.name}: {exc.message}"
            ) from exc

