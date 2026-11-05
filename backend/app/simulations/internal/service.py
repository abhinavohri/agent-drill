"""Simulation run lifecycle and ordered event recording."""

from uuid import uuid4

from pydantic import JsonValue

from app.simulations.internal.models import (
    RunEventType,
    RunRecord,
    RunStatus,
    SimulationRun,
)
from app.simulations.internal.sandbox import Sandbox


class RunNotFoundError(LookupError):
    pass


class RunNotActiveError(RuntimeError):
    pass


class ActionLimitExceededError(RuntimeError):
    pass


class SimulationService:
    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox
        self._runs: dict[str, RunRecord] = {}

    async def start_run(self, scenario_id: str, max_actions: int = 20) -> SimulationRun:
        if max_actions < 1:
            raise ValueError("max_actions must be greater than zero")

        run_id = str(uuid4())
        sandbox_id = await self._sandbox.prepare(run_id, scenario_id)
        record = RunRecord(
            id=run_id,
            scenario_id=scenario_id,
            sandbox_id=sandbox_id,
            status=RunStatus.RUNNING,
            max_actions=max_actions,
        )
        record.append(RunEventType.RUN_STARTED, {"scenarioId": scenario_id})
        self._runs[run_id] = record
        return record.snapshot()

    def get_run(self, run_id: str) -> SimulationRun:
        return self._get_record(run_id).snapshot()

    def record_tool_call(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> None:
        record = self._get_active_record(run_id)
        if record.action_count >= record.max_actions:
            raise ActionLimitExceededError(f"Run {run_id} reached its action limit")

        record.action_count += 1
        record.append(
            RunEventType.TOOL_CALL,
            {"tool": tool_name, "arguments": arguments},
        )

    def record_tool_result(
        self,
        run_id: str,
        tool_name: str,
        result: dict[str, JsonValue],
    ) -> None:
        record = self._get_active_record(run_id)
        record.append(RunEventType.TOOL_RESULT, {"tool": tool_name, "result": result})

    def record_message(self, run_id: str, role: str, content: str) -> None:
        record = self._get_active_record(run_id)
        record.append(RunEventType.MESSAGE, {"role": role, "content": content})

    def record_state_change(
        self,
        run_id: str,
        tool_name: str,
        change: dict[str, JsonValue],
    ) -> None:
        record = self._get_active_record(run_id)
        record.append(RunEventType.STATE_CHANGED, {"tool": tool_name, "change": change})

    def record_tool_error(self, run_id: str, tool_name: str, message: str) -> None:
        record = self._get_active_record(run_id)
        record.append(RunEventType.TOOL_ERROR, {"tool": tool_name, "message": message})

    async def complete_run(
        self,
        run_id: str,
        final_state: dict[str, JsonValue],
    ) -> SimulationRun:
        record = self._get_active_record(run_id)
        record.status = RunStatus.COMPLETED
        record.final_state = final_state
        record.append(RunEventType.RUN_COMPLETED, {})
        await self._sandbox.cleanup(record.sandbox_id)
        return record.snapshot()

    async def fail_run(self, run_id: str, message: str) -> SimulationRun:
        record = self._get_active_record(run_id)
        record.status = RunStatus.FAILED
        record.append(RunEventType.RUN_FAILED, {"message": message})
        await self._sandbox.cleanup(record.sandbox_id)
        return record.snapshot()

    async def stop_run(self, run_id: str) -> SimulationRun:
        record = self._get_active_record(run_id)
        record.status = RunStatus.STOPPED
        record.append(RunEventType.RUN_STOPPED, {})
        await self._sandbox.cleanup(record.sandbox_id)
        return record.snapshot()

    def _get_record(self, run_id: str) -> RunRecord:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise RunNotFoundError(f"Run {run_id} does not exist") from exc

    def _get_active_record(self, run_id: str) -> RunRecord:
        record = self._get_record(run_id)
        if record.status is not RunStatus.RUNNING:
            raise RunNotActiveError(f"Run {run_id} is not active")
        return record

