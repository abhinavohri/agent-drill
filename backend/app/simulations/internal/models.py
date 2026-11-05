"""Stable simulation models and private run state."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue


class RunStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class RunEventType(StrEnum):
    RUN_STARTED = "run_started"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    RUN_STOPPED = "run_stopped"


class RunEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    type: RunEventType
    payload: dict[str, JsonValue]
    created_at: datetime


class SimulationRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    scenario_id: str
    sandbox_id: str
    status: RunStatus
    action_count: int
    max_actions: int
    events: tuple[RunEvent, ...]


@dataclass
class RunRecord:
    id: str
    scenario_id: str
    sandbox_id: str
    status: RunStatus
    max_actions: int
    action_count: int = 0
    events: list[RunEvent] = field(default_factory=list)

    def append(self, event_type: RunEventType, payload: dict[str, JsonValue]) -> None:
        self.events.append(
            RunEvent(
                sequence=len(self.events) + 1,
                type=event_type,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        )

    def snapshot(self) -> SimulationRun:
        return SimulationRun(
            id=self.id,
            scenario_id=self.scenario_id,
            sandbox_id=self.sandbox_id,
            status=self.status,
            action_count=self.action_count,
            max_actions=self.max_actions,
            events=tuple(self.events),
        )

