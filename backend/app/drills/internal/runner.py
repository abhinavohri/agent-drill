"""Run a target command and validate its ATIF artifact."""

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from re import Match
from time import monotonic
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.drills.internal.models import (
    PLACEHOLDER_PATTERN,
    CommandRunnerConfig,
    DrillRun,
    DrillRunStatus,
    TargetPlaceholder,
    TargetRunContext,
)
from app.traces.facade import TraceInputError, load_atif


class DrillRunner(Protocol):
    def run(self, context: TargetRunContext) -> DrillRun: ...


class DrillConfigError(ValueError):
    pass


@dataclass(frozen=True)
class TargetRunValues:
    scenario_id: str
    task: str | None
    mcp_url: str | None
    trace_path: Path
    output_dir: Path
    policy_file: Path | None


class CommandDrillRunner:
    def __init__(self, config: CommandRunnerConfig) -> None:
        self._config = config

    def run(self, context: TargetRunContext) -> DrillRun:
        started_at = datetime.now(UTC)
        started = monotonic()
        try:
            values = self._values(context)
            command = tuple(_render(part, values) for part in self._config.command)
        except ValueError as exc:
            return self._result(
                context.scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                error=str(exc),
            )
        missing = [name for name in self._config.inherit_environment if name not in os.environ]
        if missing:
            return self._result(
                context.scenario_id,
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
                context.scenario_id,
                DrillRunStatus.TIMED_OUT,
                started_at,
                started,
                stdout=_text(exc.stdout),
                stderr=_text(exc.stderr),
                error=f"Target command exceeded {self._config.timeout_seconds:g} seconds",
            )
        except OSError as exc:
            return self._result(
                context.scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                error=f"Cannot start target command: {exc}",
            )
        if process.returncode != 0:
            return self._result(
                context.scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                error=f"Target command exited with code {process.returncode}",
            )
        trace_path = values.trace_path
        try:
            trace = load_atif(trace_path)
        except TraceInputError as exc:
            return self._result(
                context.scenario_id,
                DrillRunStatus.FAILED,
                started_at,
                started,
                exit_code=0,
                stdout=process.stdout,
                stderr=process.stderr,
                error=str(exc),
            )
        return self._result(
            context.scenario_id,
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

    def _values(self, context: TargetRunContext) -> TargetRunValues:
        configured_path = str(self._config.trace_path).replace(
            "{scenario_id}", context.scenario_id
        )
        path = context.trace_path or Path(configured_path)
        path = path if path.is_absolute() else self._config.working_directory / path
        path = path.resolve()
        policy_file = context.policy_file
        if policy_file is not None:
            if not policy_file.is_absolute():
                policy_file = self._config.working_directory / policy_file
            policy_file = policy_file.resolve()
        return TargetRunValues(
            scenario_id=context.scenario_id,
            task=context.task,
            mcp_url=context.mcp_url,
            trace_path=path,
            output_dir=path.parent,
            policy_file=policy_file,
        )

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


def _render(text: str, values: TargetRunValues) -> str:
    def replace(match: Match[str]) -> str:
        placeholder = TargetPlaceholder(match.group(1))
        value = _placeholder_value(placeholder, values)
        if value is None:
            raise ValueError(f"Target adapter requires {{{placeholder.value}}}")
        return value

    return PLACEHOLDER_PATTERN.sub(replace, text)


def _placeholder_value(placeholder: TargetPlaceholder, values: TargetRunValues) -> str | None:
    match placeholder:
        case TargetPlaceholder.SCENARIO_ID:
            return values.scenario_id
        case TargetPlaceholder.TASK:
            return values.task
        case TargetPlaceholder.MCP_URL:
            return values.mcp_url
        case TargetPlaceholder.TRACE_PATH:
            return str(values.trace_path)
        case TargetPlaceholder.OUTPUT_DIR:
            return str(values.output_dir)
        case TargetPlaceholder.POLICY_FILE:
            return None if values.policy_file is None else str(values.policy_file)


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
