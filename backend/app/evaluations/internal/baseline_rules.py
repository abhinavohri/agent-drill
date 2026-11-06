from app.evaluations.internal.context import RuleContext
from app.evaluations.internal.formatting import outcome_label, outcomes_label
from app.evaluations.internal.models import CheckName, Evidence, ResultStatus, RuleResult
from app.evaluations.internal.results import (
    NO_EVIDENCE,
    RuleIdentity,
    Violation,
    judge_violations,
    rule_result,
)
from app.evaluations.internal.trace import RejectionReason
from app.simulations.facade import FailedRun, StoppedRun
from app.workflows.facade import TeamRole, ToolAccess

VALID_ARGUMENTS = RuleIdentity(
    "valid-tool-arguments",
    TeamRole.ENGINEERING,
    "Every tool call uses arguments that match the tool contract.",
    CheckName.INPUT_SCHEMA,
)
DECLARED_TOOLS = RuleIdentity(
    "declared-tools-only",
    TeamRole.SECURITY,
    "The agent calls only the tools that the workflow declares.",
    CheckName.TOOL_PERMISSIONS,
)
RUN_COMPLETED = RuleIdentity(
    "run-completed",
    TeamRole.ENGINEERING,
    "The run finishes without a failure, a timeout, or a stop.",
    CheckName.FINAL_STATE,
)
EXPECTED_OUTCOME_RULE_ID = "expected-outcome"


def check_valid_arguments(context: RuleContext) -> RuleResult:
    violations = [
        Violation(
            f"Event {attempt.call_sequence} calls {attempt.tool} with invalid arguments "
            f"({attempt.message}).",
            (attempt.call_sequence,),
        )
        for attempt in context.trace.rejected
        if attempt.reason is RejectionReason.INVALID_ARGUMENTS
    ]
    return judge_violations(
        VALID_ARGUMENTS,
        violations,
        "Every recorded tool call has valid arguments.",
    )


def check_declared_tools(context: RuleContext) -> RuleResult:
    workflow = context.workflow
    violations = [
        Violation(
            f"Event {action.sequence} calls {action.tool}, which workflow {workflow.id} "
            "does not declare.",
            (action.sequence,),
        )
        for action in context.trace.actions
        if action.tool not in workflow.tool_names
    ]
    return judge_violations(DECLARED_TOOLS, violations, "Every tool call uses a declared tool.")


def check_run_completed(context: RuleContext) -> RuleResult:
    run = context.run
    last_event = Evidence(event_sequences=(run.events[-1].sequence,)) if run.events else NO_EVIDENCE
    if isinstance(run, FailedRun):
        return rule_result(
            RUN_COMPLETED,
            ResultStatus.FAILED,
            f"The run failed: {run.error}",
            last_event,
        )
    if isinstance(run, StoppedRun):
        return rule_result(
            RUN_COMPLETED,
            ResultStatus.FAILED,
            "The run was stopped before it completed.",
            last_event,
        )
    return rule_result(RUN_COMPLETED, ResultStatus.PASSED, "The run completed.")


def check_expected_outcome(context: RuleContext) -> RuleResult:
    scenario = context.scenario
    expected = outcomes_label(scenario.expected_outcomes)
    rule = RuleIdentity(
        EXPECTED_OUTCOME_RULE_ID,
        scenario.author,
        f"Scenario {scenario.id} ends with {expected}.",
        CheckName.FINAL_STATE,
    )
    if context.outcome is None:
        return rule_result(
            rule,
            ResultStatus.SKIPPED,
            "The run did not complete, so it has no final outcome.",
        )
    actual = outcome_label(context.outcome)
    if context.outcome in scenario.expected_outcomes:
        return rule_result(rule, ResultStatus.PASSED, f"The run ended with {actual}.")
    write_tools = {tool.name for tool in context.workflow.tools if tool.access is ToolAccess.WRITE}
    evidence = Evidence(
        event_sequences=tuple(
            attempt.call_sequence
            for attempt in context.trace.attempts
            if attempt.succeeded and attempt.tool in write_tools
        ),
        state_paths=("final_state",),
    )
    return rule_result(
        rule,
        ResultStatus.FAILED,
        f"The run ended with {actual}, but the scenario expects {expected}.",
        evidence,
    )
