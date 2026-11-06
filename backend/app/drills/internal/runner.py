"""Run a target command and validate its ATIF artifact."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.drills.internal.models import CommandRunnerConfig, DrillRun, DrillRunStatus
from app.traces.facade import TraceInputError, load_atif


class DrillRunner(Protocol):
    def run(self, scenario_id: str) -> DrillRun: ...


class DrillConfigError(ValueError):
    pass


class CommandDrillRunner:
    def __init__(self, config: CommandRunnerConfig) -> None:
        self._config = config

    def run(self, scenario_id: str) -> DrillRun:
        started_at = datetime.now(UTC)
        started = monotonic()
        command = tuple(part.replace("{scenario_id}", scenario_id) for part in self._config.command)
        missing = [name for name in self._config.inherit_environment if name not in os.environ]
        if missing:
            return self._result(
                scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                error=f"Required environment variable is not set: {', '.join(missing)}",
            )
        environment = {
            name: os.environ[name] for name in self._config.inherit_environment
        } | self._config.environment
        try:
            process = subprocess.run(
                command,
                cwd=self._config.working_directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=self._config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return self._result(
                scenario_id,
                DrillRunStatus.TIMED_OUT,
                started_at,
                started,
                stdout=_text(exc.stdout),
                stderr=_text(exc.stderr),
                error=f"Target command exceeded {self._config.timeout_seconds:g} seconds",
            )
        except OSError as exc:
            return self._result(
                scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                error=f"Cannot start target command: {exc}",
            )
        if process.returncode != 0:
            return self._result(
                scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                error=f"Target command exited with code {process.returncode}",
            )
        trace_path = self._trace_path(scenario_id)
        try:
            trace = load_atif(trace_path)
        except TraceInputError as exc:
            return self._result(
                scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                exit_code=0,
                stdout=process.stdout,
                stderr=process.stderr,
                error=str(exc),
            )
        return self._result(
            scenario_id,
            DrillRunStatus.COMPLETED,
            started_at,
            started,
            exit_code=0,
            stdout=process.stdout,
            stderr=process.stderr,
            trace_path=trace_path,
            agent_name=trace.agent.name,
            agent_version=trace.agent.version,
        )

    def _trace_path(self, scenario_id: str) -> Path:
        value = str(self._config.trace_path).replace("{scenario_id}", scenario_id)
        path = Path(value)
        return path if path.is_absolute() else self._config.working_directory / path

    @staticmethod
    def _result(
        scenario_id: str,
        status: DrillRunStatus,
        started_at: datetime,
        started: float,
        **values: object,
    ) -> DrillRun:
        return DrillRun(
            id=uuid4().hex,
            scenario_id=scenario_id,
            status=status,
            started_at=started_at,
            duration_ms=int((monotonic() - started) * 1000),
            **values,
        )


def load_command_config(path: Path) -> CommandRunnerConfig:
    try:
        data = json.loads(path.read_text())
        config = CommandRunnerConfig.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DrillConfigError(f"Invalid drill configuration {path}: {exc}") from exc
    working_directory = config.working_directory
    if not working_directory.is_absolute():
        working_directory = path.parent / working_directory
    return config.model_copy(update={"working_directory": working_directory.resolve()})


def _text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""
