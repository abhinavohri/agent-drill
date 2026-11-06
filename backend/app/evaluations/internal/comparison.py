from app.evaluations.internal.models import (
    ComparedRun,
    ResultStatus,
    RuleChange,
    RunComparison,
    RunResult,
)


class ComparisonError(ValueError):
    pass


def compare_results(original: RunResult, rerun: RunResult) -> RunComparison:
    original_identity = (original.agent_id, original.workflow_id, original.scenario_id)
    rerun_identity = (rerun.agent_id, rerun.workflow_id, rerun.scenario_id)
    if original_identity != rerun_identity:
        raise ComparisonError("A rerun must use the agent, workflow, and scenario of the original run")
    if original.run_id == rerun.run_id:
        raise ComparisonError(f"Run {rerun.run_id} cannot be compared with itself")
    before = _rule_statuses(original)
    after = _rule_statuses(rerun)
    changes = tuple(
        RuleChange(rule_id=rule_id, before=before[rule_id], after=status)
        for rule_id, status in after.items()
        if rule_id in before and before[rule_id] is not status
    )
    return RunComparison(
        agent_id=rerun.agent_id,
        workflow_id=rerun.workflow_id,
        scenario_id=rerun.scenario_id,
        original=_compared_run(original),
        rerun=_compared_run(rerun),
        rule_changes=changes,
    )


def _rule_statuses(result: RunResult) -> dict[str, ResultStatus]:
    return {rule.rule_id: rule.status for check in result.checks for rule in check.rules}


def _compared_run(result: RunResult) -> ComparedRun:
    return ComparedRun(
        run_id=result.run_id,
        agent_version=result.agent_version,
        verdict=result.verdict,
        outcome=result.outcome,
        tools=tuple(action.tool for action in result.actions),
        metrics=result.metrics,
    )
