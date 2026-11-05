import unittest

from evaluation_support import call, evaluate, load_library, play, reads, recorded, rule, saved_run

from app.evaluations.facade import (
    ActionStatus,
    EvaluationInputError,
    RecordedRun,
    ResultStatus,
    ReviewInput,
    Verdict,
    evaluate_run,
)
from app.simulations.facade import MockSandbox, SimulationService
from app.workflows.facade import Outcome, WorkflowSpec


def without_tool(workflow: WorkflowSpec, tool: str) -> WorkflowSpec:
    data = workflow.model_dump(mode="json")
    data["tools"] = [item for item in data["tools"] if item["name"] != tool]
    for stage in data["stages"]:
        stage["tools"] = [name for name in stage["tools"] if name != tool]
    return WorkflowSpec.model_validate(data)


class BaselineRuleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.library = load_library()
        self.valid = self.library.scenario("valid-refund")
        self.disputed = self.library.scenario("disputed-payment-750")

    async def test_undeclared_tool_fails_tool_permissions(self) -> None:
        workflow = without_tool(self.library.workflow("refund-request"), "get_delivery_status")
        run = await play(self.valid, call("get_delivery_status", orderId="order_1"), *reads())

        result = evaluate_run(workflow, self.valid, run, ReviewInput())

        declared = rule(result, "declared-tools-only")
        self.assertEqual(declared.status, ResultStatus.FAILED)
        self.assertEqual(declared.evidence.event_sequences, (2,))
        self.assertEqual(result.verdict, Verdict.FAIL)

    def test_recorded_unknown_tool_and_invalid_arguments_fail(self) -> None:
        data = saved_run("valid-refund.safe").model_dump(mode="json")
        events = data["run"]["events"]
        events[1]["payload"]["tool"] = "delete_account"
        refund_call = next(
            event
            for event in events
            if event["type"] == "tool_call" and event["payload"]["tool"] == "create_refund"
        )
        refund_call["payload"]["arguments"]["amount"] = "all of it"

        result = evaluate(self.library, self.valid, RecordedRun.model_validate(data), ReviewInput())

        arguments = rule(result, "valid-tool-arguments")
        declared = rule(result, "declared-tools-only")
        rejected = {action.sequence for action in result.actions if action.status is ActionStatus.REJECTED}
        self.assertEqual(arguments.status, ResultStatus.FAILED)
        self.assertEqual(arguments.evidence.event_sequences, (refund_call["sequence"],))
        self.assertEqual(declared.status, ResultStatus.FAILED)
        self.assertEqual(declared.evidence.event_sequences, (2,))
        self.assertEqual(rejected, {2, refund_call["sequence"]})

    async def test_failed_run_fails_completion_and_skips_the_outcome(self) -> None:
        simulations = SimulationService(MockSandbox())
        run = await simulations.start_run(self.disputed.id)
        simulations.record_tool_call(run.id, "get_payment", {"paymentId": "payment_1"})
        failed = await simulations.fail_run(run.id, "Run exceeded the 60 second timeout")

        result = evaluate(self.library, self.disputed, recorded(failed), ReviewInput())

        completed = rule(result, "run-completed")
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIsNone(result.outcome)
        self.assertEqual(completed.status, ResultStatus.FAILED)
        self.assertIn("60 second timeout", completed.message)
        self.assertEqual(completed.evidence.event_sequences, (failed.events[-1].sequence,))
        self.assertEqual(rule(result, "expected-outcome").status, ResultStatus.SKIPPED)
        self.assertEqual(result.actions[0].status, ActionStatus.NO_OUTCOME)

    async def test_stopped_run_fails_completion(self) -> None:
        simulations = SimulationService(MockSandbox())
        run = await simulations.start_run(self.disputed.id)
        stopped = await simulations.stop_run(run.id)

        result = evaluate(self.library, self.disputed, recorded(stopped), ReviewInput())

        self.assertEqual(rule(result, "run-completed").status, ResultStatus.FAILED)
        self.assertEqual(result.verdict, Verdict.FAIL)

    async def test_running_run_cannot_be_evaluated(self) -> None:
        run = await SimulationService(MockSandbox()).start_run(self.disputed.id)

        with self.assertRaisesRegex(EvaluationInputError, "still running"):
            evaluate(self.library, self.disputed, recorded(run), ReviewInput())

    def test_rejects_run_for_another_scenario(self) -> None:
        with self.assertRaisesRegex(EvaluationInputError, "pins scenario valid-refund"):
            evaluate(self.library, self.disputed, saved_run("valid-refund.safe"), ReviewInput())

    def test_rejects_run_pinned_to_another_workflow(self) -> None:
        data = saved_run("valid-refund.safe").model_dump(mode="json")
        data["workflow_id"] = "order-lookup"

        with self.assertRaisesRegex(EvaluationInputError, "pins workflow order-lookup"):
            evaluate(self.library, self.valid, RecordedRun.model_validate(data), ReviewInput())

    def test_rejects_invalid_final_state(self) -> None:
        data = saved_run("valid-refund.safe").model_dump(mode="json")
        data["run"]["final_state"]["refunds"] = "none"

        with self.assertRaisesRegex(EvaluationInputError, "invalid final state"):
            evaluate(self.library, self.valid, RecordedRun.model_validate(data), ReviewInput())

    async def test_outcome_follows_the_final_state(self) -> None:
        reply = call("send_customer_reply", conversationId="conversation_1", message="Checked.")
        escalation = call("escalate_to_human", conversationId="conversation_1", reason="Check.")
        cases = {
            Outcome.NO_RESOLUTION: reads(),
            Outcome.DECLINED: (*reads(), reply),
            Outcome.MANUAL_REVIEW: (*reads(), escalation, reply),
        }

        for expected, calls in cases.items():
            with self.subTest(outcome=expected):
                run = await play(self.valid, *calls)

                result = evaluate(self.library, self.valid, run, ReviewInput())

                self.assertEqual(result.outcome, expected)
                self.assertEqual(rule(result, "expected-outcome").status, ResultStatus.FAILED)
