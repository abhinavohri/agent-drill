from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, JsonValue, ValidationError

from app.evaluations.internal.models import ActionStatus, ActionSummary
from app.refunds.facade import REFUND_TOOL_ARGUMENTS
from app.simulations.facade import (
    RunEvent,
    StateChangedPayload,
    ToolCallPayload,
    ToolErrorPayload,
    ToolResultPayload,
)


class RejectionReason(StrEnum):
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"


@dataclass(frozen=True)
class ToolAttempt:
    call_sequence: int
    tool: str
    arguments: BaseModel
    status: ActionStatus
    related_sequences: tuple[int, ...]

    @property
    def succeeded(self) -> bool:
        return self.status is ActionStatus.SUCCEEDED

    @property
    def evidence_sequences(self) -> tuple[int, ...]:
        return (self.call_sequence, *self.related_sequences)


@dataclass(frozen=True)
class RejectedAttempt:
    call_sequence: int
    tool: str
    reason: RejectionReason
    message: str


@dataclass(frozen=True)
class RunTrace:
    attempts: tuple[ToolAttempt, ...]
    rejected: tuple[RejectedAttempt, ...]
    actions: tuple[ActionSummary, ...]


@dataclass
class _RecordedCall:
    sequence: int
    tool: str
    arguments: dict[str, JsonValue]
    status: ActionStatus = ActionStatus.NO_OUTCOME
    related: list[int] = field(default_factory=list)


def build_trace(events: Sequence[RunEvent]) -> RunTrace:
    attempts: list[ToolAttempt] = []
    rejected: list[RejectedAttempt] = []
    actions: list[ActionSummary] = []
    for call in _recorded_calls(events):
        classified = _classify(call)
        if isinstance(classified, ToolAttempt):
            attempts.append(classified)
            status = call.status
        else:
            rejected.append(classified)
            status = ActionStatus.REJECTED
        actions.append(
            ActionSummary(
                sequence=call.sequence,
                tool=call.tool,
                arguments=call.arguments,
                status=status,
            )
        )
    return RunTrace(tuple(attempts), tuple(rejected), tuple(actions))


def _recorded_calls(events: Sequence[RunEvent]) -> list[_RecordedCall]:
    calls: list[_RecordedCall] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, ToolCallPayload):
            calls.append(_RecordedCall(event.sequence, payload.tool, payload.arguments))
        elif isinstance(payload, ToolResultPayload | ToolErrorPayload):
            call = _latest_call(calls, payload.tool, awaiting_outcome=True)
            if call is not None:
                succeeded = isinstance(payload, ToolResultPayload)
                call.status = ActionStatus.SUCCEEDED if succeeded else ActionStatus.FAILED
                call.related.append(event.sequence)
        elif isinstance(payload, StateChangedPayload):
            call = _latest_call(calls, payload.tool, awaiting_outcome=False)
            if call is not None:
                call.related.append(event.sequence)
    return calls


def _latest_call(
    calls: list[_RecordedCall],
    tool: str,
    *,
    awaiting_outcome: bool,
) -> _RecordedCall | None:
    for call in reversed(calls):
        if call.tool != tool:
            continue
        if awaiting_outcome and call.status is not ActionStatus.NO_OUTCOME:
            return None
        return call
    return None


def _classify(call: _RecordedCall) -> ToolAttempt | RejectedAttempt:
    argument_model = REFUND_TOOL_ARGUMENTS.get(call.tool)
    if argument_model is None:
        return RejectedAttempt(
            call.sequence,
            call.tool,
            RejectionReason.UNKNOWN_TOOL,
            f"{call.tool} is not a refund tool",
        )
    try:
        arguments = argument_model.model_validate(call.arguments)
    except ValidationError as exc:
        error = exc.errors()[0]
        location = ".".join(str(part) for part in error["loc"]) or "arguments"
        return RejectedAttempt(
            call.sequence,
            call.tool,
            RejectionReason.INVALID_ARGUMENTS,
            f"{location}: {error['msg']}",
        )
    return ToolAttempt(
        call.sequence,
        call.tool,
        arguments,
        call.status,
        tuple(call.related),
    )
