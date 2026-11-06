import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from evaluation_support import evaluate, load_library, recorded, saved_run

from app.evaluations.facade import (
    ComparisonError,
    Decision,
    ResultStatus,
    ReviewDecision,
    ReviewInput,
    RunMetrics,
    RunResult,
    Verdict,
    compare_results,
    render_comparison,
    render_run_report,
)
from app.jobs.build_refund_fixtures import LIBRARY_ROOT
from app.jobs.evaluate_run import main
from app.simulations.facade import MockSandbox, SimulationService
from app.workflows.facade import TeamRole

FINANCE_APPROVAL = ReviewInput(
    decisions=(
        ReviewDecision(
            reviewer="finance_reviewer_1",
            role=TeamRole.FINANCE,
            decision=Decision.APPROVE,
        ),
    )
)


class ReportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.library = load_library()
        self.scenario = self.library.scenario("disputed-payment-750")
        self.unsafe = saved_run("disputed-payment-750.unsafe")
        self.safe = saved_run("disputed-payment-750.safe")

    def test_failing_report_names_the_unsafe_call_and_links_evidence(self) -> None:
        result = evaluate(self.library, self.scenario, self.unsafe, ReviewInput())

        report = render_run_report(result, self.unsafe, self.scenario)

        refund_call = next(action for action in result.actions if action.tool == "create_refund")
        self.assertIn("**Verdict: FAIL.**", report)
        self.assertIn(
            f'First failure: event {refund_call.sequence}, '
            '`create_refund(paymentId="payment_1", amount=75000)`',
            report,
        )
        for failed in result.failed_rules():
            self.assertIn(f"**{failed.rule_id}**", report)
            for sequence in failed.evidence.event_sequences:
                self.assertIn(f"[event {sequence}](#event-{sequence})", report)
                self.assertIn(f'<a id="event-{sequence}"></a>', report)
        self.assertIn('"status": "disputed"', report)
        self.assertNotIn("## Approval request", report)

    def test_review_report_requests_finance_approval(self) -> None:
        result = evaluate(self.library, self.scenario, self.safe, ReviewInput())

        report = render_run_report(result, self.safe, self.scenario)

        self.assertIn("**Verdict: REVIEW.**", report)
        self.assertIn("## Approval request", report)
        self.assertIn("Approval requested from finance.", report)
        self.assertIn("**customer-reply-review**", report)
        self.assertNotIn("## Failed rules", report)

    def test_passing_report_has_no_failures_or_open_requests(self) -> None:
        result = evaluate(self.library, self.scenario, self.safe, FINANCE_APPROVAL)

        report = render_run_report(result, self.safe, self.scenario)

        self.assertIn("**Verdict: PASS.**", report)
        self.assertNotIn("## Failed rules", report)
        self.assertNotIn("## Approval request", report)

    async def test_incomplete_run_report_explains_the_missing_final_state(self) -> None:
        simulations = SimulationService(MockSandbox())
        run = await simulations.start_run(self.scenario.id)
        failed = recorded(await simulations.fail_run(run.id, "Run exceeded the action limit"))

        report = render_run_report(
            evaluate(self.library, self.scenario, failed, ReviewInput()),
            failed,
            self.scenario,
        )

        self.assertIn("The run failed: Run exceeded the action limit", report)
        self.assertIn("Not available, because the run did not complete.", report)

    def test_comparison_lists_the_fixed_rules(self) -> None:
        original = evaluate(self.library, self.scenario, self.unsafe, ReviewInput()).model_copy(
            update={
                "metrics": RunMetrics(
                    duration_ms=4200,
                    total_prompt_tokens=1000,
                    total_completion_tokens=200,
                    total_cost_usd=0.0021,
                    llm_calls=4,
                )
            }
        )
        rerun = evaluate(self.library, self.scenario, self.safe, FINANCE_APPROVAL).model_copy(
            update={
                "metrics": RunMetrics(
                    duration_ms=4800,
                    total_prompt_tokens=1200,
                    total_completion_tokens=250,
                    total_cached_tokens=600,
                    total_cost_usd=0.0024,
                    llm_calls=5,
                )
            }
        )

        comparison = compare_results(original, rerun)

        fixed = {
            change.rule_id
            for change in comparison.rule_changes
            if change.before is ResultStatus.FAILED and change.after is ResultStatus.PASSED
        }
        self.assertEqual(
            fixed,
            {"no-refund-disputed-payment", "refund-approval-limit", "expected-outcome"},
        )
        rendered = render_comparison(comparison)
        self.assertIn("| Verdict | FAIL | PASS |", rendered)
        self.assertIn("| Agent version | `v1` | `v2` |", rendered)
        self.assertIn("| Duration | 4.20 s | 4.80 s |", rendered)
        self.assertIn("| Cost | $0.002100 | $0.002400 |", rendered)
        self.assertIn("| LLM calls | 4 | 5 |", rendered)
        self.assertIn("Regressed rules: none", rendered)

    def test_comparison_requires_the_same_scenario_and_two_runs(self) -> None:
        original = evaluate(self.library, self.scenario, self.unsafe, ReviewInput())
        valid = self.library.scenario("valid-refund")
        other = evaluate(self.library, valid, saved_run("valid-refund.safe"), ReviewInput())

        with self.assertRaises(ComparisonError):
            compare_results(original, other)
        with self.assertRaises(ComparisonError):
            compare_results(original, original)


class EvaluateRunCommandTests(unittest.TestCase):
    def test_prints_the_report_and_writes_the_result(self) -> None:
        runs = LIBRARY_ROOT / "runs"
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        str(runs / "disputed-payment-750.safe.json"),
                        "--review",
                        str(LIBRARY_ROOT / "reviews" / "disputed-payment-750.safe.json"),
                        "--compare-with",
                        str(runs / "disputed-payment-750.unsafe.json"),
                        "--result-json",
                        str(result_path),
                    ]
                )

            result = RunResult.model_validate_json(result_path.read_text())

        self.assertEqual(code, 0)
        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertIn("**Verdict: PASS.**", output.getvalue())
        self.assertIn("## Original run compared with rerun", output.getvalue())

    def test_writes_the_report_to_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.md"
            main(
                [
                    str(LIBRARY_ROOT / "runs" / "duplicate-refund.unsafe.json"),
                    "--report",
                    str(report_path),
                ]
            )

            report = report_path.read_text()

        self.assertIn("**no-duplicate-refund**", report)

    def test_rejects_a_missing_run_file(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["missing-run.json"])

        self.assertEqual(raised.exception.code, 2)
