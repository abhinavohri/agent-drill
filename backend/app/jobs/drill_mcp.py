"""Run the local stdio Drill MCP proxy with explicit mock providers."""

import asyncio

from app.drill_mcp.facade import DrillProxyService, MockUpstreamToolClient, run_stdio_server
from app.simulations.facade import MockSandbox, SimulationService


async def main() -> None:
    simulations = SimulationService(MockSandbox())
    run = await simulations.start_run("local-mock")
    proxy = DrillProxyService(MockUpstreamToolClient(), simulations)
    await proxy.initialize()

    try:
        await run_stdio_server(proxy, run.id)
    finally:
        await proxy.close()
        if simulations.get_run(run.id).status.value == "running":
            await simulations.stop_run(run.id)


if __name__ == "__main__":
    asyncio.run(main())

