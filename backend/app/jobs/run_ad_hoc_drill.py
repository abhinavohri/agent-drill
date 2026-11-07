"""Run a real target against one declarative ad hoc scenario."""

import argparse
import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from app.drills.facade import (
    CommandDrillRunner,
    DrillConfigError,
    DrillRun,
    DrillRunStatus,
    TargetRunContext,
    load_command_config,
)
from app.jobs.refund_runtime import run_refund_target
from app.refunds.facade import prepare_refund_scenario
from app.simulations.facade import SimulationRun
from app.traces.facade import Trajectory, load_atif
from app.workflows.facade import AdHocScenario, DirectEnvironment


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_command_config(args.config)
        scenario = AdHocScenario.model_validate_json(args.scenario.read_text())
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        (output / "scenario.json").write_text(scenario.model_dump_json(indent=2) + "\n")
    except (OSError, ValidationError, DrillConfigError) as exc:
        parser.error(str(exc))

    if isinstance(scenario.environment, DirectEnvironment):
        drill = CommandDrillRunner(config).run(
            TargetRunContext(
                scenario_id=scenario.id,
                task=scenario.task,
                trace_path=output / "trajectory.json",
            )
        )
        simulation = None
    else:
        prepared = prepare_refund_scenario(scenario.id, scenario.environment)
        task = f"{scenario.task}\nSupport conversation ID: {prepared.conversation_id}."
        drill, simulation = asyncio.run(
            run_refund_target(
                config,
                prepared.scenario,
                task,
                output / "trajectory.json",
            )
        )

    (output / "drill-run.json").write_text(
        drill.model_dump_json(indent=2, exclude_none=True) + "\n"
    )
    if simulation is not None:
        (output / "simulation-run.json").write_text(simulation.model_dump_json(indent=2) + "\n")
    trace = load_atif(drill.trace_path) if drill.trace_path is not None else None
    response = _final_response(trace) if trace is not None else drill.error or "Target failed."
    (output / "report.md").write_text(_report(scenario, drill, simulation, response))
    sys.stdout.write(f"{scenario.id}: {drill.status}\n{response}\nArtifacts: {output}\n")
    return 0 if drill.status is DrillRunStatus.COMPLETED else 1


def _final_response(trace: Trajectory) -> str:
    for step in reversed(trace.steps):
        if step.source != "agent":
            continue
        if isinstance(step.message, str):
            return step.message
        return "\n".join(part.text or "" for part in step.message if part.type == "text")
    return "Agent returned no response."


def _report(
    scenario: AdHocScenario,
    drill: DrillRun,
    simulation: SimulationRun | None,
    response: str,
) -> str:
    actions = simulation.action_count if simulation is not None else 0
    return (
        "# Ad hoc drill result\n\n"
        f"- Scenario: `{scenario.id}`\n"
        f"- Environment: `{scenario.environment.kind}`\n"
        f"- Target status: `{drill.status}`\n"
        f"- Duration: `{drill.duration_ms} ms`\n"
        f"- Tool actions: `{actions}`\n\n"
        "## Agent response\n\n"
        f"{response}\n"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.jobs.run_ad_hoc_drill",
        description="Run a target against a generated scenario without production services.",
    )
    parser.add_argument("config", type=Path, help="target command configuration JSON")
    parser.add_argument("scenario", type=Path, help="declarative scenario JSON")
    parser.add_argument("--output", type=Path, required=True, help="artifact output directory")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
