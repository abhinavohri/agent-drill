"""Simulation run snapshots and private lifecycle state."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.simulations.internal.events import EventPayload, RunEvent, RunEventType


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class RunSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    scenario_id: str
    sandbox_id: str
    action_count: int
    max_actions: int
    events: tuple[RunEvent, ...]


class RunningRun(RunSnapshot):
    status: Literal[RunStatus.RUNNING] = RunStatus.RUNNING


class CompletedRun(RunSnapshot):
    status: Literal[RunStatus.COMPLETED] = RunStatus.COMPLETED
    final_state: dict[str, JsonValue]


class StoppedRun(RunSnapshot):
    status: Literal[RunStatus.STOPPED] = RunStatus.STOPPED


class FailedRun(RunSnapshot):
    status: Literal[RunStatus.FAILED] = RunStatus.FAILED
    error: str


SimulationRun = Annotated[
    RunningRun | CompletedRun | StoppedRun | FailedRun,
    Field(discriminator="status"),
]


@dataclass
class RunRecord:
    id: str
    scenario_id: str
    sandbox_id: str
    status: RunStatus
    max_actions: int
    action_count: int = 0
    events: list[RunEvent] = field(default_factory=list)
    final_state: dict[str, JsonValue] | None = None
    error: str | None = None

    def append(self, event_type: RunEventType, payload: EventPayload) -> None:
        self.events.append(
            RunEvent(
                sequence=len(self.events) + 1,
                type=event_type,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        )

    def complete(self, final_state: dict[str, JsonValue]) -> None:
        self.status = RunStatus.COMPLETED
        self.final_state = final_state

    def fail(self, message: str) -> None:
        self.status = RunStatus.FAILED
        self.error = message

    def stop(self) -> None:
        self.status = RunStatus.STOPPED

    def snapshot(self) -> SimulationRun:
        if self.status is RunStatus.RUNNING:
            return RunningRun(
                id=self.id,
                scenario_id=self.scenario_id,
                sandbox_id=self.sandbox_id,
                action_count=self.action_count,
                max_actions=self.max_actions,
                events=tuple(self.events),
            )
        if self.status is RunStatus.COMPLETED:
            assert self.final_state is not None
            return CompletedRun(
                id=self.id,
                scenario_id=self.scenario_id,
                sandbox_id=self.sandbox_id,
                action_count=self.action_count,
                max_actions=self.max_actions,
                events=tuple(self.events),
                final_state=self.final_state,
            )
        if self.status is RunStatus.FAILED:
            assert self.error is not None
            return FailedRun(
                id=self.id,
                scenario_id=self.scenario_id,
                sandbox_id=self.sandbox_id,
                action_count=self.action_count,
                max_actions=self.max_actions,
                events=tuple(self.events),
                error=self.error,
            )
        return StoppedRun(
            id=self.id,
            scenario_id=self.scenario_id,
            sandbox_id=self.sandbox_id,
            action_count=self.action_count,
            max_actions=self.max_actions,
            events=tuple(self.events),
        )

