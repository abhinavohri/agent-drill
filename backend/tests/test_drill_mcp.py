import unittest

from app.drill_mcp.facade import (
    DrillProxyService,
    InvalidToolArgumentsError,
    MockUpstreamToolClient,
    ToolNotAllowedError,
    UpstreamToolTimeoutError,
)
from app.simulations.facade import (
    ActionLimitExceededError,
    MockSandbox,
    RunEventType,
    RunStatus,
    SimulationService,
)


class DrillProxyServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.sandbox = MockSandbox()
        self.simulations = SimulationService(self.sandbox)
        self.run = await self.simulations.start_run("proxy-test")
        self.upstream = MockUpstreamToolClient()
        self.proxy = DrillProxyService(self.upstream, self.simulations)
        await self.proxy.initialize()

    async def asyncTearDown(self) -> None:
        await self.proxy.close()

    async def test_imports_and_forwards_upstream_tool(self) -> None:
        result = await self.proxy.call_tool(
            self.run.id,
            "get_payment",
            {"paymentId": "pay_1"},
        )

        self.assertEqual(result.data["provider"], "mock")
        self.assertEqual(self.upstream.calls, [("get_payment", {"paymentId": "pay_1"})])
        events = self.simulations.get_run(self.run.id).events
        self.assertEqual(events[-2].type, RunEventType.TOOL_CALL)
        self.assertEqual(events[-1].type, RunEventType.TOOL_RESULT)

    async def test_rejects_unknown_tool_before_upstream_call(self) -> None:
        with self.assertRaises(ToolNotAllowedError):
            await self.proxy.call_tool(self.run.id, "delete_account", {})

        self.assertEqual(self.upstream.calls, [])

    async def test_rejects_invalid_arguments(self) -> None:
        with self.assertRaises(InvalidToolArgumentsError):
            await self.proxy.call_tool(self.run.id, "get_payment", {})

        self.assertEqual(self.upstream.calls, [])

    async def test_records_upstream_timeout(self) -> None:
        proxy = DrillProxyService(
            MockUpstreamToolClient(delay_seconds=0.05),
            self.simulations,
            timeout_seconds=0.001,
        )
        await proxy.initialize()

        with self.assertRaises(UpstreamToolTimeoutError):
            await proxy.call_tool(self.run.id, "get_payment", {"paymentId": "pay_1"})

        self.assertEqual(
            self.simulations.get_run(self.run.id).events[-1].type,
            RunEventType.TOOL_ERROR,
        )
        await proxy.close()

    async def test_action_limit_fails_run_and_cleans_sandbox(self) -> None:
        limited = await self.simulations.start_run("limited", max_actions=1)
        await self.proxy.call_tool(limited.id, "get_payment", {"paymentId": "pay_1"})

        with self.assertRaises(ActionLimitExceededError):
            await self.proxy.call_tool(limited.id, "get_payment", {"paymentId": "pay_2"})

        failed = self.simulations.get_run(limited.id)
        self.assertEqual(failed.status, RunStatus.FAILED)
        self.assertNotIn(limited.sandbox_id, self.sandbox.active_ids)

