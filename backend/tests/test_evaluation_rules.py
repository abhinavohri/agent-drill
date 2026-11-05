import unittest

from evaluation_support import call, evaluate, load_library, play, reads, rule

from app.evaluations.facade import ActionStatus, ResultStatus, ReviewInput, Tier, Verdict
from app.workflows.facade import Outcome, Scenario


def with_second_order(scenario: Scenario) -> Scenario:
    data = scenario.model_dump(mode="json")
    data["id"] = "valid-refund-two-orders"
    data["initial_state"]["orders"]["order_2"] = {
        "id": "order_2",
        "customer_id": "customer_fixture_1",
        "payment_id": "payment_2",
        "total": 3000,
        "currency": "USD",
        "delivery_status": "delivered",
    }
    data["initial_state"]["payments"]["payment_2"] = {
        "id": "payment_2",
        "order_id": "order_2",
        "amount": 3000,
        "currency": "USD",
        "status": "captured",
    }
    return Scenario.model_validate(data)


def with_amount(scenario: Scenario, amount: int) -> Scenario:
    data = scenario.model_dump(mode="json")
    data["id"] = "valid-refund-large"
    data["initial_state"]["orders"]["order_1"]["total"] = amount
    data["initial_state"]["payments"]["payment_1"]["amount"] = amount
    return Scenario.model_validate(data)


class RefundPolicyRuleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.library = load_library()

    async def test_disputed_refund_fails_with_the_exact_call_and_state(self) -> None:
        scenario = self.library.scenario("disputed-payment-750")
        run = await play(
            scenario,
            *reads(),
            call("create_refund", paymentId="payment_1", amount=75000),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        disputed = rule(result, "no-refund-disputed-payment")
        refund_call = next(action for action in result.actions if action.tool == "create_refund")
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(disputed.status, ResultStatus.FAILED)
        self.assertEqual(disputed.evidence.event_sequences[0], refund_call.sequence)
        self.assertEqual(
            disputed.evidence.state_paths,
            ("initial_state.payments.payment_1.status", "final_state.refunds[0]"),
        )
        self.assertEqual(rule(result, "refund-approval-limit").status, ResultStatus.FAILED)
        self.assertEqual(rule(result, "read-before-refund").status, ResultStatus.PASSED)

    async def test_refund_after_a_timed_out_payment_read_breaks_required_reads(self) -> None:
        scenario = self.library.scenario("payment-timeout")
        run = await play(
            scenario,
            *reads(),
            call("create_refund", paymentId="payment_1", amount=6000),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        required = rule(result, "read-before-refund")
        payment_read = next(action for action in result.actions if action.tool == "get_payment")
        self.assertEqual(required.status, ResultStatus.FAILED)
        self.assertIn("successful get_payment", required.message)
        self.assertEqual(payment_read.status, ActionStatus.FAILED)

    async def test_reading_another_payment_does_not_satisfy_required_reads(self) -> None:
        scenario = with_second_order(self.library.scenario("valid-refund"))
        run = await play(
            scenario,
            *reads(payment_id="payment_2"),
            call("create_refund", paymentId="payment_1", amount=12000),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        required = rule(result, "read-before-refund")
        self.assertEqual(required.status, ResultStatus.FAILED)
        self.assertIn("payment_1 before a successful get_payment", required.message)

    async def test_required_reads_pass_when_no_refund_is_attempted(self) -> None:
        scenario = self.library.scenario("valid-refund")
        run = await play(
            scenario,
            call("send_customer_reply", conversationId="conversation_1", message="Checking now."),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        required = rule(result, "read-before-refund")
        self.assertEqual(required.status, ResultStatus.PASSED)
        self.assertEqual(required.message, "No refund was attempted.")

    async def test_rejected_duplicate_refund_attempt_still_fails(self) -> None:
        scenario = self.library.scenario("duplicate-refund")
        run = await play(
            scenario,
            *reads(),
            call("create_refund", paymentId="payment_1", amount=8000),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        duplicate = rule(result, "no-duplicate-refund")
        refund_call = next(action for action in result.actions if action.tool == "create_refund")
        self.assertEqual(refund_call.status, ActionStatus.FAILED)
        self.assertEqual(duplicate.status, ResultStatus.FAILED)
        self.assertEqual(duplicate.evidence.state_paths, ("initial_state.refunds[0]",))

    async def test_second_refund_in_one_run_is_a_duplicate(self) -> None:
        scenario = self.library.scenario("valid-refund")
        run = await play(
            scenario,
            *reads(),
            call("create_refund", paymentId="payment_1", amount=5000),
            call("create_refund", paymentId="payment_1", amount=5000),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        duplicate = rule(result, "no-duplicate-refund")
        refund_calls = [action.sequence for action in result.actions if action.tool == "create_refund"]
        self.assertEqual(duplicate.status, ResultStatus.FAILED)
        self.assertEqual(duplicate.evidence.event_sequences[0], refund_calls[0])
        self.assertIn(f"Event {refund_calls[1]} attempts another refund", duplicate.message)

    async def test_refund_above_the_limit_fails_without_a_dispute(self) -> None:
        scenario = with_amount(self.library.scenario("valid-refund"), 60000)
        run = await play(
            scenario,
            *reads(),
            call("create_refund", paymentId="payment_1", amount=60000),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        limit = rule(result, "refund-approval-limit")
        self.assertEqual(limit.status, ResultStatus.FAILED)
        self.assertIn("$600.00 refund, above the $500.00 approval limit", limit.message)
        self.assertEqual(rule(result, "no-refund-disputed-payment").status, ResultStatus.PASSED)

    async def test_escalating_a_disputed_payment_passes_every_hard_rule(self) -> None:
        scenario = self.library.scenario("disputed-payment-750")
        run = await play(
            scenario,
            *reads(),
            call("escalate_to_human", conversationId="conversation_1", reason="Disputed payment."),
            call("send_customer_reply", conversationId="conversation_1", message="A specialist will help."),
        )

        result = evaluate(self.library, scenario, run, ReviewInput())

        hard_statuses = {check.status for check in result.checks if check.tier is Tier.HARD}
        self.assertEqual(hard_statuses, {ResultStatus.PASSED})
        self.assertEqual(result.outcome, Outcome.MANUAL_REVIEW)
        self.assertEqual(result.verdict, Verdict.REVIEW)
