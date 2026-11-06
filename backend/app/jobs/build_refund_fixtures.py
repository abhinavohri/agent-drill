import asyncio
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

from pydantic import BaseModel

from app.drill_mcp.facade import DrillProxyService, ToolProviderError, ToolProviderTimeoutError
from app.evaluations.facade import (
    RecordedRun,
    ReviewInput,
    RunResult,
    compare_results,
    evaluate_run,
    render_comparison,
    render_run_report,
)
from app.refunds.facade import RefundScenario, RefundToolProvider, RefundWorld
from app.simulations.facade import MockSandbox, SimulationService
from app.workflows.facade import AgentScript, Scenario, ScenarioLibrary, load_scenario_library

LIBRARY_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "refunds"


async def record_script(script: AgentScript, scenario: Scenario) -> RecordedRun:
    world = RefundWorld(
        RefundScenario(
            id=scenario.id,
            initial_state=scenario.initial_state,
            faults=list(scenario.faults),
        )
    )
    simulations = SimulationService(MockSandbox())
    run = await simulations.start_run(scenario.id)
    proxy = DrillProxyService(RefundToolProvider(world), simulations)
    await proxy.initialize()
    try:
        for call in script.calls:
            with suppress(ToolProviderError, ToolProviderTimeoutError):
                await proxy.call_tool(run.id, call.tool, call.arguments)
        completed = await simulations.complete_run(run.id, world.snapshot())
    finally:
        await proxy.close()
    return RecordedRun(
        agent_id=script.agent_id,
        agent_version=script.agent_version,
        workflow_id=scenario.workflow_id,
        run=completed,
    )


def fixture_outputs(
    library: ScenarioLibrary,
    root: Path,
    runs: Mapping[str, RecordedRun],
) -> dict[Path, str]:
    results: dict[str, RunResult] = {}
    outputs: dict[Path, str] = {}
    for script in sorted(library.scripts.values(), key=lambda item: (item.rerun_of is not None, item.id)):
        recorded = runs[script.id]
        scenario = library.scenario(script.scenario_id)
        workflow = library.workflow(recorded.workflow_id)
        result = evaluate_run(workflow, scenario, recorded, _review_input(root, script.id))
        results[script.id] = result
        report = render_run_report(result, recorded, scenario)
        if script.rerun_of is not None:
            comparison = compare_results(results[script.rerun_of], result)
            report = f"{report}\n{render_comparison(comparison)}"
        outputs[root / "runs" / f"{script.id}.json"] = _json(recorded)
        outputs[root / "results" / f"{script.id}.json"] = _json(result)
        outputs[root / "reports" / f"{script.id}.md"] = report
    return outputs


async def build_fixtures(root: Path) -> None:
    library = load_scenario_library(root)
    runs = {
        script.id: await record_script(script, library.scenario(script.scenario_id))
        for script in library.scripts.values()
    }
    for path, content in fixture_outputs(library, root, runs).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _review_input(root: Path, script_id: str) -> ReviewInput:
    path = root / "reviews" / f"{script_id}.json"
    if not path.exists():
        return ReviewInput()
    return ReviewInput.model_validate_json(path.read_text())


def _json(model: BaseModel) -> str:
    return model.model_dump_json(indent=2, exclude_none=True) + "\n"


if __name__ == "__main__":
    asyncio.run(build_fixtures(LIBRARY_ROOT))
