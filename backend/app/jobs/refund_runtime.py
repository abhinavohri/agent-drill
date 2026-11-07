"""Compose one real target run with a synthetic refund world."""

import asyncio
from pathlib import Path

from app.drill_mcp.facade import DrillProxyService, serve_streamable_http
from app.drills.facade import CommandDrillRunner, CommandRunnerConfig, DrillRun, TargetRunContext
from app.refunds.facade import RefundScenario, RefundToolProvider, RefundWorld
from app.simulations.facade import MockSandbox, RunStatus, SimulationRun, SimulationService


async def run_refund_target(
    config: CommandRunnerConfig,
    scenario: RefundScenario,
    task: str,
    trace_path: Path,
    policy_file: Path | None = None,
) -> tuple[DrillRun, SimulationRun]:
    world = RefundWorld(scenario)
    simulations = SimulationService(MockSandbox())
    run = await simulations.start_run(scenario.id)
    proxy = DrillProxyService(RefundToolProvider(world), simulations)
    await proxy.initialize()
    try:
        async with serve_streamable_http(proxy, run.id) as url:
            context = TargetRunContext(
                scenario_id=scenario.id,
                task=task,
                mcp_url=url,
                trace_path=trace_path,
                policy_file=policy_file,
            )
            drill = await asyncio.to_thread(CommandDrillRunner(config).run, context)
        if simulations.get_run(run.id).status is RunStatus.RUNNING:
            finished = await simulations.complete_run(run.id, world.snapshot())
        else:
            finished = simulations.get_run(run.id)
    finally:
        await proxy.close()
    return drill, finished
