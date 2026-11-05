import unittest

from app.simulations.facade import (
    ActionLimitExceededError,
    MockSandbox,
    RunEventType,
    RunStatus,
    SimulationService,
)


class SimulationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.sandbox = MockSandbox()
        self.service = SimulationService(self.sandbox)

    async def test_records_ordered_events_and_cleans_sandbox(self) -> None:
        run = await self.service.start_run("disputed-refund", max_actions=2)

        self.service.record_tool_call(run.id, "get_payment", {"paymentId": "pay_1"})
        self.service.record_tool_result(run.id, "get_payment", {"status": "disputed"})
        stopped = await self.service.stop_run(run.id)

        self.assertEqual(stopped.status, RunStatus.STOPPED)
        self.assertEqual([event.sequence for event in stopped.events], [1, 2, 3, 4])
        self.assertEqual(
            [event.type for event in stopped.events],
            [
                RunEventType.RUN_STARTED,
                RunEventType.TOOL_CALL,
                RunEventType.TOOL_RESULT,
                RunEventType.RUN_STOPPED,
            ],
        )
        self.assertNotIn(run.sandbox_id, self.sandbox.active_ids)

    async def test_enforces_action_limit(self) -> None:
        run = await self.service.start_run("one-action", max_actions=1)
        self.service.record_tool_call(run.id, "get_payment", {"paymentId": "pay_1"})

        with self.assertRaises(ActionLimitExceededError):
            self.service.record_tool_call(run.id, "get_payment", {"paymentId": "pay_2"})

    async def test_records_message_and_completed_final_state(self) -> None:
        run = await self.service.start_run("completed-run")
        self.service.record_message(run.id, "assistant", "Review required.")

        completed = await self.service.complete_run(run.id, {"refunds": []})

        self.assertEqual(completed.status, RunStatus.COMPLETED)
        self.assertEqual(completed.final_state, {"refunds": []})
        self.assertEqual(completed.events[-2].type, RunEventType.MESSAGE)
        self.assertEqual(completed.events[-1].type, RunEventType.RUN_COMPLETED)
        self.assertNotIn(run.sandbox_id, self.sandbox.active_ids)

