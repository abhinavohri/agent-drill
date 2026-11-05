"""Typed simulation event contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class RunEventType(StrEnum):
    RUN_STARTED = "run_started"
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    STATE_CHANGED = "state_changed"
    RUN_COMPLETED = "run_completed"
    RUN_STOPPED = "run_stopped"
    RUN_FAILED = "run_failed"


class EventModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class StateChange(EventModel):
    resource: str
    operation: str
    value: dict[str, JsonValue]


class RunStartedPayload(EventModel):
    scenario_id: str = Field(alias="scenarioId")


class MessagePayload(EventModel):
    role: str
    content: str


class ToolCallPayload(EventModel):
    tool: str
    arguments: dict[str, JsonValue]


class ToolResultPayload(EventModel):
    tool: str
    result: dict[str, JsonValue]


class ToolErrorPayload(EventModel):
    tool: str
    message: str


class StateChangedPayload(EventModel):
    tool: str
    change: StateChange


class RunFailedPayload(EventModel):
    message: str


class EmptyPayload(EventModel):
    pass


EventPayload = (
    RunStartedPayload
    | MessagePayload
    | ToolCallPayload
    | ToolResultPayload
    | ToolErrorPayload
    | StateChangedPayload
    | RunFailedPayload
    | EmptyPayload
)

PAYLOAD_TYPES: dict[RunEventType, type[EventModel]] = {
    RunEventType.RUN_STARTED: RunStartedPayload,
    RunEventType.MESSAGE: MessagePayload,
    RunEventType.TOOL_CALL: ToolCallPayload,
    RunEventType.TOOL_RESULT: ToolResultPayload,
    RunEventType.TOOL_ERROR: ToolErrorPayload,
    RunEventType.STATE_CHANGED: StateChangedPayload,
    RunEventType.RUN_COMPLETED: EmptyPayload,
    RunEventType.RUN_STOPPED: EmptyPayload,
    RunEventType.RUN_FAILED: RunFailedPayload,
}


class RunEvent(EventModel):
    sequence: int = Field(ge=1)
    type: RunEventType
    payload: EventPayload
    created_at: datetime

    @model_validator(mode="after")
    def payload_matches_event_type(self) -> "RunEvent":
        expected = PAYLOAD_TYPES[self.type]
        if not isinstance(self.payload, expected):
            raise ValueError(f"{self.type} requires {expected.__name__}")
        return self
