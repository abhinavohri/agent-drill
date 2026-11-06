from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.refunds.facade import REFUND_TOOL_ARGUMENTS
from app.workflows.internal.models import AgentScript, LibraryRecord, Scenario, WorkflowSpec


class LibraryError(ValueError):
    pass


class UnknownRecordError(LookupError):
    pass


@dataclass(frozen=True)
class ScenarioLibrary:
    workflows: dict[str, WorkflowSpec]
    scenarios: dict[str, Scenario]
    scripts: dict[str, AgentScript]

    def workflow(self, workflow_id: str) -> WorkflowSpec:
        return _lookup(self.workflows, "Workflow", workflow_id)

    def scenario(self, scenario_id: str) -> Scenario:
        return _lookup(self.scenarios, "Scenario", scenario_id)

    def script(self, script_id: str) -> AgentScript:
        return _lookup(self.scripts, "Agent script", script_id)


def load_scenario_library(root: Path) -> ScenarioLibrary:
    library = ScenarioLibrary(
        workflows=_load_records(root / "workflows", WorkflowSpec),
        scenarios=_load_records(root / "scenarios", Scenario),
        scripts=_load_records(root / "agent_scripts", AgentScript),
    )
    for workflow in library.workflows.values():
        _check_workflow(workflow)
    for scenario in library.scenarios.values():
        _check_scenario(scenario, library)
    for script in library.scripts.values():
        _check_script(script, library)
    return library


def _load_records[RecordT: LibraryRecord](
    directory: Path,
    model: type[RecordT],
) -> dict[str, RecordT]:
    records: dict[str, RecordT] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            record = model.model_validate_json(path.read_text())
        except ValidationError as exc:
            raise LibraryError(f"{path.name} is invalid: {exc}") from exc
        if record.id != path.stem:
            raise LibraryError(f"{path.name} must contain id {path.stem}, not {record.id}")
        records[record.id] = record
    return records


def _check_workflow(workflow: WorkflowSpec) -> None:
    unknown = sorted(workflow.tool_names - set(REFUND_TOOL_ARGUMENTS))
    if unknown:
        raise LibraryError(f"Workflow {workflow.id} declares unknown tools: {', '.join(unknown)}")


def _check_scenario(scenario: Scenario, library: ScenarioLibrary) -> None:
    workflow = _reference(library.workflows, scenario.workflow_id, f"Scenario {scenario.id}")
    invalid_outcomes = sorted(set(scenario.expected_outcomes) - set(workflow.outcomes))
    if invalid_outcomes:
        raise LibraryError(
            f"Scenario {scenario.id} expects outcomes outside workflow {workflow.id}: "
            f"{', '.join(invalid_outcomes)}"
        )
    fault_tools = sorted({fault.tool for fault in scenario.faults} - workflow.tool_names)
    if fault_tools:
        raise LibraryError(
            f"Scenario {scenario.id} injects faults into undeclared tools: {', '.join(fault_tools)}"
        )


def _check_script(script: AgentScript, library: ScenarioLibrary) -> None:
    _reference(library.scenarios, script.scenario_id, f"Agent script {script.id}")
    if script.rerun_of is None:
        return
    original = _reference(library.scripts, script.rerun_of, f"Agent script {script.id}")
    if original.rerun_of is not None:
        raise LibraryError(f"Agent script {script.id} must rerun an original script")
    if (original.scenario_id, original.agent_id) != (script.scenario_id, script.agent_id):
        raise LibraryError(
            f"Agent script {script.id} must rerun the same scenario and agent as {original.id}"
        )


def _lookup[RecordT](records: dict[str, RecordT], label: str, record_id: str) -> RecordT:
    try:
        return records[record_id]
    except KeyError as exc:
        raise UnknownRecordError(f"{label} {record_id} does not exist") from exc


def _reference[RecordT](records: dict[str, RecordT], record_id: str, owner: str) -> RecordT:
    try:
        return records[record_id]
    except KeyError as exc:
        raise LibraryError(f"{owner} references missing record {record_id}") from exc
