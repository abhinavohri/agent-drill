"""Typed command-runner input and drill-run output."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from re import compile as compile_pattern
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DrillModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetPlaceholder(StrEnum):
    SCENARIO_ID = "scenario_id"
    TASK = "task"
    MCP_URL = "mcp_url"
    TRACE_PATH = "trace_path"
    OUTPUT_DIR = "output_dir"
    POLICY_FILE = "policy_file"


PLACEHOLDER_PATTERN = compile_pattern(r"\{([a-z][a-z0-9_]*)\}")
COMMAND_PLACEHOLDERS = frozenset(TargetPlaceholder)
TRACE_PATH_PLACEHOLDERS = frozenset((TargetPlaceholder.SCENARIO_ID,))


class CommandRunnerConfig(DrillModel):
    kind: Literal["command"] = "command"
    command: tuple[str, ...] = Field(min_length=1)
    working_directory: Path
    inherit_environment: tuple[str, ...] = ("PATH",)
    environment: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(gt=0)
    trace_path: Path

    @model_validator(mode="after")
    def placeholders_are_supported(self) -> Self:
        for part in self.command:
            _validate_placeholders(part, COMMAND_PLACEHOLDERS, "command")
        _validate_placeholders(str(self.trace_path), TRACE_PATH_PLACEHOLDERS, "trace_path")
        return self


class TargetRunContext(DrillModel):
    scenario_id: str = Field(min_length=1)
    task: str | None = Field(default=None, min_length=1)
    mcp_url: str | None = Field(default=None, min_length=1)
    trace_path: Path | None = None
    policy_file: Path | None = None


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


def _validate_placeholders(
    text: str,
    allowed: frozenset[TargetPlaceholder],
    field: str,
) -> None:
    names = {match.group(1) for match in PLACEHOLDER_PATTERN.finditer(text)}
    unknown = sorted(names - {placeholder.value for placeholder in allowed})
    if unknown:
        raise ValueError(f"Unsupported {field} placeholders: {', '.join(unknown)}")
