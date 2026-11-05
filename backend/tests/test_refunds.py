import json
import unittest
from pathlib import Path

from app.drill_mcp.facade import DrillProxyService, RefundWorldToolClient
from app.refunds.facade import RefundScenario, RefundWorld, load_refund_scenario
from app.simulations.facade import MockSandbox, RunEventType, RunStatus, SimulationService

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "stubs"


class RefundWorldTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.scenario = load_refund_scenario(FIXTURE_ROOT / "refund-scenario.json")
        self.world = RefundWorld(self.scenario)

    async def test_exposes_all_refund_tools(self) -> None:
        self.assertEqual(
            {tool.name for tool in self.world.list_tools()},
            {
                "get_conversation",
                "get_order",
                "get_payment",
                "get_delivery_status",
                "get_refund_history",
                "create_refund",
                "send_customer_reply",
                "escalate_to_human",
            },
        )

    async def test_mutates_and_returns_refund_state(self) -> None:
        payment = await self.world.call_tool("get_payment", {"paymentId": "payment_1"})
        self.assertEqual(payment.data["status"], "disputed")

        created = await self.world.call_tool(
            "create_refund",
            {"paymentId": "payment_1", "amount": 75000},
        )
        await self.world.call_tool(
            "send_customer_reply",
            {"conversationId": "conversation_1", "message": "Refund issued."},
        )
        await self.world.call_tool(
            "escalate_to_human",
            {"conversationId": "conversation_1", "reason": "Disputed payment."},
        )

        state = self.world.snapshot()
        self.assertEqual(created.data["id"], "refund_1")
        self.assertEqual(len(state["refunds"]), 1)
        self.assertEqual(len(state["customer_replies"]), 1)
        self.assertEqual(len(state["human_escalations"]), 1)

    async def test_unsafe_refund_matches_evaluator_handoff_fixture(self) -> None:
        await self.world.call_tool(
            "create_refund",
            {"paymentId": "payment_1", "amount": 75000},
        )
        expected = json.loads((FIXTURE_ROOT / "final-state.json").read_text())

        self.assertEqual(self.world.snapshot(), expected)

    async def test_new_world_starts_from_clean_fixture_state(self) -> None:
        await self.world.call_tool(
            "create_refund",
            {"paymentId": "payment_1", "amount": 75000},
        )

        clean_world = RefundWorld(self.scenario)

        self.assertEqual(clean_world.snapshot()["refunds"], [])

    async def test_injects_configured_tool_fault_once(self) -> None:
        data = self.scenario.model_dump(mode="json")
        data["faults"] = [
            {
                "tool": "get_payment",
                "kind": "timeout",
                "times": 1,
                "message": "Payment service timed out",
            }
        ]
        world = RefundWorld(RefundScenario.model_validate(data))

        with self.assertRaises(TimeoutError):
            await world.call_tool("get_payment", {"paymentId": "payment_1"})

        result = await world.call_tool("get_payment", {"paymentId": "payment_1"})
        self.assertEqual(result.data["id"], "payment_1")

    async def test_proxy_records_state_change_and_final_state(self) -> None:
        sandbox = MockSandbox()
        simulations = SimulationService(sandbox)
        run = await simulations.start_run(self.scenario.id)
        proxy = DrillProxyService(RefundWorldToolClient(self.world), simulations)
        await proxy.initialize()

        await proxy.call_tool(
            run.id,
            "create_refund",
            {"paymentId": "payment_1", "amount": 75000},
        )
        completed = await simulations.complete_run(run.id, self.world.snapshot())

        self.assertEqual(completed.status, RunStatus.COMPLETED)
        self.assertEqual(completed.events[-2].type, RunEventType.STATE_CHANGED)
        self.assertEqual(completed.events[-1].type, RunEventType.RUN_COMPLETED)
        self.assertEqual(len(completed.final_state["refunds"]), 1)
        self.assertNotIn(run.sandbox_id, sandbox.active_ids)
        await proxy.close()
