from dataclasses import dataclass

from pydantic import ValidationError

from app.evaluations.internal.models import RecordedRun
from app.evaluations.internal.trace import RunTrace, build_trace
from app.refunds.facade import RefundState
from app.simulations.facade import CompletedRun, RunStatus, SimulationRun
from app.workflows.facade import Outcome, Scenario, WorkflowSpec


class EvaluationInputError(ValueError):
    pass


@dataclass(frozen=True)
class RuleContext:
    workflow: WorkflowSpec
    scenario: Scenario
    run: SimulationRun
    trace: RunTrace
    final_state: RefundState | None
    outcome: Outcome | None


def build_context(
    workflow: WorkflowSpec,
    scenario: Scenario,
    recorded: RecordedRun,
) -> RuleContext:
    _require_pinned_identity(workflow, scenario, recorded)
    final_state = _final_state(recorded.run)
    outcome = None if final_state is None else derive_outcome(scenario.initial_state, final_state)
    return RuleContext(
        workflow=workflow,
        scenario=scenario,
        run=recorded.run,
        trace=build_trace(recorded.run.events),
        final_state=final_state,
        outcome=outcome,
    )


def derive_outcome(initial: RefundState, final: RefundState) -> Outcome:
    initial_refunds = {refund.id for refund in initial.refunds}
    if any(refund.id not in initial_refunds for refund in final.refunds):
        return Outcome.REFUND_ISSUED
    if len(final.human_escalations) > len(initial.human_escalations):
        return Outcome.MANUAL_REVIEW
    if len(final.customer_replies) > len(initial.customer_replies):
        return Outcome.DECLINED
    return Outcome.NO_RESOLUTION


def new_item_paths(collection: str, initial_count: int, final_count: int) -> tuple[str, ...]:
    return tuple(f"final_state.{collection}[{index}]" for index in range(initial_count, final_count))


def _require_pinned_identity(
    workflow: WorkflowSpec,
    scenario: Scenario,
    recorded: RecordedRun,
) -> None:
    run = recorded.run
    if scenario.workflow_id != workflow.id:
        raise EvaluationInputError(
            f"Scenario {scenario.id} belongs to workflow {scenario.workflow_id}, not {workflow.id}"
        )
    if recorded.workflow_id != workflow.id:
        raise EvaluationInputError(
            f"Run {run.id} pins workflow {recorded.workflow_id}, not {workflow.id}"
        )
    if run.scenario_id != scenario.id:
        raise EvaluationInputError(
            f"Run {run.id} pins scenario {run.scenario_id}, not {scenario.id}"
        )
    if run.status is RunStatus.RUNNING:
        raise EvaluationInputError(f"Run {run.id} is still running")


def _final_state(run: SimulationRun) -> RefundState | None:
    if not isinstance(run, CompletedRun):
        return None
    try:
        return RefundState.model_validate(run.final_state)
    except ValidationError as exc:
        raise EvaluationInputError(f"Run {run.id} has an invalid final state: {exc}") from exc
