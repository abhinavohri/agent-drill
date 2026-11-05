"""Run the local stdio Drill MCP proxy with explicit mock providers."""

import asyncio
from pathlib import Path

from app.drill_mcp.facade import DrillProxyService, run_stdio_server
from app.refunds.facade import RefundToolProvider, RefundWorld, load_refund_scenario
from app.simulations.facade import MockSandbox, SimulationService

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stubs"


async def main() -> None:
    scenario = load_refund_scenario(FIXTURE_ROOT / "refund-scenario.json")
    world = RefundWorld(scenario)
    simulations = SimulationService(MockSandbox())
    run = await simulations.start_run(scenario.id)
    proxy = DrillProxyService(RefundToolProvider(world), simulations)
    await proxy.initialize()

    try:
        async with asyncio.timeout(60):
            await run_stdio_server(proxy, run.id)
    except TimeoutError:
        await simulations.fail_run(run.id, "Run exceeded the 60 second timeout")
        raise
    except Exception as exc:
        if simulations.get_run(run.id).status.value == "running":
            await simulations.fail_run(run.id, str(exc))
        raise
    else:
        await simulations.complete_run(run.id, world.snapshot())
    finally:
        await proxy.close()


if __name__ == "__main__":
    asyncio.run(main())

