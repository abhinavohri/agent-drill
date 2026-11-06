import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from app.drill_mcp.facade import DrillProxyService, serve_streamable_http
from app.drills.facade import (
    CommandDrillRunner,
    CommandRunnerConfig,
    DrillConfigError,
    DrillRun,
    DrillRunStatus,
    load_command_config,
)
from app.evaluations.facade import (
    EvaluationInputError,
    RecordedRun,
    ReviewInput,
    evaluate_run,
    render_run_report,
)
from app.refunds.facade import RefundScenario, RefundToolProvider, RefundWorld
from app.simulations.facade import MockSandbox, RunStatus, SimulationRun, SimulationService
from app.workflows.facade import (
    LibraryError,
    Scenario,
    UnknownRecordError,
    WorkflowSpec,
    load_scenario_library,
)

LIBRARY_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "refunds"
UNIDENTIFIED_AGENT = "unidentified-target"
UNKNOWN_VERSION = "unknown"


@dataclass(frozen=True)
class TargetValues:
    mcp_url: str
    output_dir: Path
    policy_file: Path
    conversation_id: str

    def fill(self, text: str) -> str:
        return (
            text.replace("{mcp_url}", self.mcp_url)
            .replace("{output_dir}", str(self.output_dir))
            .replace("{policy_file}", str(self.policy_file))
            .replace("{conversation_id}", self.conversation_id)
        )

    def apply(self, config: CommandRunnerConfig) -> CommandRunnerConfig:
        return config.model_copy(
            update={
                "command": tuple(self.fill(part) for part in config.command),
                "trace_path": Path(self.fill(str(config.trace_path))),
            }
        )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_command_config(args.config)
        library = load_scenario_library(args.library)
        scenario = library.scenario(args.scenario)
        workflow = library.workflow(scenario.workflow_id)
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        policy_file = output / "policy.md"
        policy_file.write_text(_policy(workflow))
    except (OSError, DrillConfigError, LibraryError, UnknownRecordError) as exc:
        parser.error(str(exc))
    drill, recorded = asyncio.run(_drill(config, scenario, output, policy_file))
    (output / "drill-run.json").write_text(drill.model_dump_json(indent=2, exclude_none=True) + "\n")
    (output / "recorded-run.json").write_text(recorded.model_dump_json(indent=2) + "\n")
    try:
        result = evaluate_run(workflow, scenario, recorded, ReviewInput())
    except EvaluationInputError as exc:
        sys.stderr.write(f"Cannot evaluate the run: {exc}\n")
        return 1
    (output / "result.json").write_text(result.model_dump_json(indent=2) + "\n")
    (output / "report.md").write_text(render_run_report(result, recorded, scenario))
    sys.stdout.write(
        f"{scenario.id}: target {drill.status}, verdict {result.verdict}, "
        f"outcome {result.outcome or 'none'}\n"
    )
    return 0 if drill.status is DrillRunStatus.COMPLETED else 1


async def _drill(
    config: CommandRunnerConfig,
    scenario: Scenario,
    output: Path,
    policy_file: Path,
) -> tuple[DrillRun, RecordedRun]:
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
        async with serve_streamable_http(proxy, run.id) as url:
            values = TargetValues(url, output, policy_file, scenario.conversation_id)
            runner = CommandDrillRunner(values.apply(config))
            drill = await asyncio.to_thread(runner.run, scenario.id)
        finished = await _finish(simulations, run.id, world)
    finally:
        await proxy.close()
    recorded = RecordedRun(
        agent_id=drill.agent_name or UNIDENTIFIED_AGENT,
        agent_version=drill.agent_version or UNKNOWN_VERSION,
        workflow_id=scenario.workflow_id,
        run=finished,
    )
    return drill, recorded


async def _finish(simulations: SimulationService, run_id: str, world: RefundWorld) -> SimulationRun:
    if simulations.get_run(run_id).status is RunStatus.RUNNING:
        return await simulations.complete_run(run_id, world.snapshot())
    return simulations.get_run(run_id)


def _policy(workflow: WorkflowSpec) -> str:
    rules = "".join(f"- {rule.policy}\n" for rule in workflow.rules)
    return f"{workflow.title} policy:\n{rules}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.jobs.run_refund_drill",
        description=(
            "Serve one refund scenario over MCP, run a target command against it, "
            "and grade the recorded run."
        ),
    )
    parser.add_argument("config", type=Path, help="command-runner configuration JSON")
    parser.add_argument("scenario", help="refund scenario identifier")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="directory for the policy, drill result, recorded run, result, and report",
    )
    parser.add_argument("--library", type=Path, default=LIBRARY_ROOT, help="scenario library root")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
