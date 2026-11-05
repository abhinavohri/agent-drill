import json

from app.evaluations.internal.formatting import (
    call_label,
    compact_json,
    join_words,
    outcome_label,
    outcomes_label,
    table_header,
    table_row,
)
from app.evaluations.internal.models import (
    CheckName,
    RecordedRun,
    ResultStatus,
    RuleResult,
    RunResult,
    Verdict,
)
from app.simulations.facade import (
    CompletedRun,
    MessagePayload,
    RunEvent,
    RunFailedPayload,
    RunStartedPayload,
    StateChangedPayload,
    ToolCallPayload,
    ToolErrorPayload,
    ToolResultPayload,
)
from app.workflows.facade import Scenario

CHECK_LABELS: dict[CheckName, str] = {
    CheckName.INPUT_SCHEMA: "Input schema",
    CheckName.TOOL_PERMISSIONS: "Tool permissions",
    CheckName.ACTION_ORDER: "Action order and invariants",
    CheckName.FINAL_STATE: "Final state",
    CheckName.SEMANTIC_OUTPUT: "Semantic output",
    CheckName.HUMAN_APPROVAL: "Human approval",
}
FINAL_STATE_SECTIONS = ("payments", "refunds", "human_escalations", "customer_replies")
PREVIEW_LIMIT = 120


def render_run_report(result: RunResult, recorded: RecordedRun, scenario: Scenario) -> str:
    sections = (
        _summary(result, scenario),
        _failed_rules(result),
        _approval_request(result),
        _checks(result),
        _trace(recorded),
        _final_state(recorded),
    )
    return "\n\n".join(section for section in sections if section) + "\n"


def _summary(result: RunResult, scenario: Scenario) -> str:
    outcome = (
        f"{outcome_label(result.outcome)} "
        f"(expected {outcomes_label(result.expected_outcomes)})"
    )
    return "\n".join(
        (
            f"# Agent Drill report: {scenario.title}",
            "",
            f"**Verdict: {result.verdict.value.upper()}.** {_headline(result)}",
            "",
            table_header("Field", "Value"),
            table_row("Agent", f"{result.agent_id} `{result.agent_version}`"),
            table_row("Workflow", result.workflow_id),
            table_row("Scenario", f"{scenario.id}, added by {scenario.author}"),
            table_row("Run", f"`{result.run_id}`"),
            table_row("Outcome", outcome),
        )
    )


def _headline(result: RunResult) -> str:
    if result.verdict is Verdict.FAIL:
        count = len(result.failed_rules())
        noun = "rule" if count == 1 else "rules"
        return f"{count} {noun} failed, so the release is blocked.{_first_failure(result)}"
    if result.verdict is Verdict.REVIEW and result.pending_approvals:
        return f"Hard rules passed. Waiting for approval from {join_words(result.pending_approvals)}."
    if result.verdict is Verdict.REVIEW:
        return "Hard rules passed. A reviewer must resolve the open checks."
    return "Every rule passed and the required approvals are recorded."


def _first_failure(result: RunResult) -> str:
    sequences = [
        sequence for rule in result.failed_rules() for sequence in rule.evidence.event_sequences
    ]
    if not sequences:
        return ""
    first = min(sequences)
    action = next((item for item in result.actions if item.sequence == first), None)
    detail = "" if action is None else f", `{call_label(action.tool, action.arguments)}`"
    return f" First failure: event {first}{detail}."


def _failed_rules(result: RunResult) -> str:
    failed = result.failed_rules()
    if not failed:
        return ""
    lines = ["## Failed rules", ""]
    for index, rule in enumerate(failed, start=1):
        lines.append(
            f"{index}. **{rule.rule_id}** ({CHECK_LABELS[rule.check]}, owner {rule.owner}): "
            f"{rule.message}"
        )
        evidence = _evidence_links(rule)
        if evidence:
            lines.append(f"   Evidence: {evidence}.")
    return "\n".join(lines)


def _evidence_links(rule: RuleResult) -> str:
    events = (f"[event {sequence}](#event-{sequence})" for sequence in rule.evidence.event_sequences)
    paths = (f"`{path}`" for path in rule.evidence.state_paths)
    return ", ".join((*events, *paths))


def _approval_request(result: RunResult) -> str:
    if result.verdict is not Verdict.REVIEW:
        return ""
    lines = ["## Approval request", ""]
    if result.pending_approvals:
        lines += [
            f"Approval requested from {join_words(result.pending_approvals)}. "
            "Approve or block this run in the Switch room.",
            "",
        ]
    lines += [
        f"- **{rule.rule_id}** (owner {rule.owner}): {rule.message}"
        for rule in result.rules_with_status(ResultStatus.OPEN)
    ]
    return "\n".join(lines)


def _checks(result: RunResult) -> str:
    rows = (
        table_row(
            CHECK_LABELS[check.check],
            check.tier.value,
            check.status.value,
            ", ".join(f"{rule.rule_id} ({rule.status.value})" for rule in check.rules) or "none",
        )
        for check in result.checks
    )
    return "\n".join(("## Checks", "", table_header("Check", "Tier", "Status", "Rules"), *rows))


def _trace(recorded: RecordedRun) -> str:
    rows = (
        table_row(
            f'<a id="event-{event.sequence}"></a>{event.sequence}',
            event.type.value.replace("_", " "),
            _describe_event(event),
        )
        for event in recorded.run.events
    )
    return "\n".join(("## Trace", "", table_header("Event", "Type", "Detail"), *rows))


def _describe_event(event: RunEvent) -> str:
    match event.payload:
        case RunStartedPayload(scenario_id=scenario_id):
            return f"Scenario {scenario_id}"
        case ToolCallPayload(tool=tool, arguments=arguments):
            return f"`{call_label(tool, arguments)}`"
        case ToolResultPayload(tool=tool, result=data):
            return f"{tool} returned {compact_json(data, PREVIEW_LIMIT)}"
        case ToolErrorPayload(tool=tool, message=message):
            return f"{tool} failed: {message}"
        case StateChangedPayload(tool=tool, change=change):
            value = compact_json(change.value, PREVIEW_LIMIT)
            return f"{tool} {change.operation} {change.resource}: {value}"
        case MessagePayload(role=role, content=content):
            return f"{role}: {content}"
        case RunFailedPayload(message=message):
            return message
    return ""


def _final_state(recorded: RecordedRun) -> str:
    run = recorded.run
    if not isinstance(run, CompletedRun):
        return "## Final synthetic state\n\nNot available, because the run did not complete."
    excerpt = {key: run.final_state[key] for key in FINAL_STATE_SECTIONS if key in run.final_state}
    state = json.dumps(excerpt, indent=2, ensure_ascii=False)
    return "\n".join(("## Final synthetic state", "", "```json", state, "```"))
