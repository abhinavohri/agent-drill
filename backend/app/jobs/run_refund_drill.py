import argparse
import asyncio
import sys
from pathlib import Path

from app.drill_mcp.facade import DrillProxyService, serve_streamable_http
from app.drills.facade import (
    CommandDrillRunner,
    CommandRunnerConfig,
    DrillConfigError,
    DrillRun,
    DrillRunStatus,
    TargetRunContext,
    load_command_config,
)
from app.evaluations.facade import (
    EvaluationInputError,
    RecordedRun,
    ReviewInput,
    RunMetrics,
    evaluate_run,
    render_run_report,
)
from app.refunds.facade import RefundScenario, RefundToolProvider, RefundWorld
from app.simulations.facade import MockSandbox, RunStatus, SimulationRun, SimulationService
from app.traces.facade import load_atif
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
        result = evaluate_run(
            workflow,
            scenario,
            recorded,
            ReviewInput(),
            metrics=_run_metrics(drill),
        )
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
            context = TargetRunContext(
                scenario_id=scenario.id,
                task=(
                    f"A customer is waiting in support conversation "
                    f"{scenario.conversation_id}. Resolve their request."
                ),
                mcp_url=url,
                trace_path=output / "trajectory.json",
                policy_file=policy_file,
            )
            drill = await asyncio.to_thread(CommandDrillRunner(config).run, context)
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


def _run_metrics(drill: DrillRun) -> RunMetrics:
    if drill.trace_path is None:
        return RunMetrics(duration_ms=drill.duration_ms)
    final = load_atif(drill.trace_path).final_metrics
    if final is None:
        return RunMetrics(duration_ms=drill.duration_ms)
    extra = final.extra or {}
    return RunMetrics(
        duration_ms=drill.duration_ms,
        total_prompt_tokens=final.total_prompt_tokens,
        total_completion_tokens=final.total_completion_tokens,
        total_cached_tokens=final.total_cached_tokens,
        total_cost_usd=final.total_cost_usd,
        total_steps=final.total_steps,
        llm_calls=_non_negative_int(extra.get("llm_calls")),
    )


def _non_negative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


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
