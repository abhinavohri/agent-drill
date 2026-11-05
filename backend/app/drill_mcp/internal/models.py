"""Stable contracts for upstream MCP tools and results."""

from pydantic import BaseModel, ConfigDict, JsonValue


class ToolDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue] | None = None


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: dict[str, JsonValue]

