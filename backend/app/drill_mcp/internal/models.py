"""Stable contracts for generic tool providers and results."""

from pydantic import BaseModel, ConfigDict, JsonValue

from app.simulations.facade import StateChange


class ToolDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue] | None = None


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: dict[str, JsonValue]
    state_change: StateChange | None = None

