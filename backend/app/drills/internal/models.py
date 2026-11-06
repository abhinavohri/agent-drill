"""Typed command-runner input and drill-run output."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DrillModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CommandRunnerConfig(DrillModel):
    kind: Literal["command"] = "command"
    command: tuple[str, ...] = Field(min_length=1)
    working_directory: Path
    inherit_environment: tuple[str, ...] = ("PATH",)
    environment: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(gt=0)
    trace_path: Path


class DrillRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class DrillRun(DrillModel):
    id: str
    scenario_id: str = Field(min_length=1)
    status: DrillRunStatus
    started_at: datetime
    duration_ms: int = Field(ge=0)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    trace_path: Path | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def state_is_complete(self) -> Self:
        trace_fields = (self.trace_path, self.agent_name, self.agent_version)
        if self.status is DrillRunStatus.COMPLETED:
            if self.exit_code != 0 or any(value is None for value in trace_fields):
                raise ValueError("A completed drill requires exit code 0 and ATIF trace metadata")
            if self.error is not None:
                raise ValueError("A completed drill cannot contain an error")
        elif self.error is None:
            raise ValueError("A failed or timed-out drill requires an error")
        return self
