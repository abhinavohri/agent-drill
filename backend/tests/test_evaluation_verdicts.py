import unittest

from evaluation_support import evaluate, load_library, rule, saved_run
from pydantic import ValidationError

from app.evaluations.facade import (
    CheckName,
    Decision,
    JudgeAssessment,
    RecordedRun,
    ResultStatus,
    ReviewDecision,
    ReviewInput,
    RunResult,
    Tier,
    Verdict,
)
from app.workflows.facade import TeamRole, WorkflowSpec

FINANCE_APPROVAL = ReviewDecision(
    reviewer="finance_reviewer_1",
    role=TeamRole.FINANCE,
    decision=Decision.APPROVE,
)
SUPPORT_APPROVAL = ReviewDecision(
    reviewer="support_reviewer_1",
    role=TeamRole.SUPPORT,
    decision=Decision.APPROVE,
)
JUDGE_CONCERN = JudgeAssessment(
    judge="reply-judge",
    acceptable=False,
    note="The reply does not say when the specialist will respond",
)
JUDGE_ACCEPTANCE = JudgeAssessment(judge="reply-judge", acceptable=True, note="Clear and accurate")


class VerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.library = load_library()
        self.scenario = self.library.scenario("disputed-payment-750")
        self.safe = saved_run("disputed-payment-750.safe")
        self.unsafe = saved_run("disputed-payment-750.unsafe")

    def review(self, run: RecordedRun, review: ReviewInput) -> RunResult:
        return evaluate(self.library, self.scenario, run, review)

    def test_safe_run_waits_for_review_without_decisions(self) -> None:
        result = self.review(self.safe, ReviewInput())

        self.assertEqual(result.verdict, Verdict.REVIEW)
        self.assertEqual(result.pending_approvals, (TeamRole.FINANCE,))
        self.assertEqual(rule(result, "customer-reply-review").status, ResultStatus.OPEN)
        self.assertEqual(rule(result, "release-approval").status, ResultStatus.OPEN)

    def test_finance_approval_passes_the_safe_run(self) -> None:
        result = self.review(self.safe, ReviewInput(decisions=(FINANCE_APPROVAL,)))

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.pending_approvals, ())

    def test_support_approval_accepts_the_reply_but_waits_for_finance(self) -> None:
        result = self.review(self.safe, ReviewInput(decisions=(SUPPORT_APPROVAL,)))

        self.assertEqual(result.verdict, Verdict.REVIEW)
        self.assertEqual(rule(result, "customer-reply-review").status, ResultStatus.PASSED)
        self.assertEqual(rule(result, "release-approval").status, ResultStatus.OPEN)
        self.assertEqual(result.pending_approvals, (TeamRole.FINANCE,))

    def test_reviewer_block_fails_the_run(self) -> None:
        block = ReviewDecision(
            reviewer="security_reviewer_1",
            role=TeamRole.SECURITY,
            decision=Decision.BLOCK,
        )

        result = self.review(self.safe, ReviewInput(decisions=(FINANCE_APPROVAL, block)))

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(rule(result, "release-approval").status, ResultStatus.FAILED)
        self.assertEqual(result.pending_approvals, ())

    def test_judge_concern_keeps_the_reply_open(self) -> None:
        result = self.review(self.safe, ReviewInput(judge_assessments=(JUDGE_CONCERN,)))

        reply = rule(result, "customer-reply-review")
        self.assertEqual(result.verdict, Verdict.REVIEW)
        self.assertEqual(reply.status, ResultStatus.OPEN)
        self.assertIn(JUDGE_CONCERN.note, reply.message)

    def test_judge_acceptance_resolves_only_the_reply(self) -> None:
        result = self.review(self.safe, ReviewInput(judge_assessments=(JUDGE_ACCEPTANCE,)))

        self.assertEqual(rule(result, "customer-reply-review").status, ResultStatus.PASSED)
        self.assertEqual(rule(result, "release-approval").status, ResultStatus.OPEN)
        self.assertEqual(result.verdict, Verdict.REVIEW)

    def test_human_approval_resolves_a_judge_concern(self) -> None:
        review = ReviewInput(decisions=(FINANCE_APPROVAL,), judge_assessments=(JUDGE_CONCERN,))

        result = self.review(self.safe, review)

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_no_review_input_overrides_a_deterministic_failure(self) -> None:
        everyone = tuple(
            ReviewDecision(reviewer=f"{role}_reviewer_1", role=role, decision=Decision.APPROVE)
            for role in TeamRole
        )
        review = ReviewInput(decisions=everyone, judge_assessments=(JUDGE_ACCEPTANCE,))

        reviewed = self.review(self.unsafe, review)
        unreviewed = self.review(self.unsafe, ReviewInput())

        hard_checks = [check for check in reviewed.checks if check.tier is Tier.HARD]
        self.assertEqual(reviewed.verdict, Verdict.FAIL)
        self.assertEqual(rule(reviewed, "release-approval").status, ResultStatus.PASSED)
        self.assertEqual(rule(reviewed, "customer-reply-review").status, ResultStatus.PASSED)
        self.assertEqual(
            hard_checks,
            [check for check in unreviewed.checks if check.tier is Tier.HARD],
        )
        self.assertEqual(reviewed.pending_approvals, ())

    def test_check_tiers_follow_the_evaluation_model(self) -> None:
        result = self.review(self.safe, ReviewInput())

        tiers = {check.check: check.tier for check in result.checks}
        self.assertEqual(
            tiers,
            {
                CheckName.INPUT_SCHEMA: Tier.HARD,
                CheckName.TOOL_PERMISSIONS: Tier.HARD,
                CheckName.ACTION_ORDER: Tier.HARD,
                CheckName.FINAL_STATE: Tier.HARD,
                CheckName.SEMANTIC_OUTPUT: Tier.REVIEW,
                CheckName.HUMAN_APPROVAL: Tier.REVIEW,
            },
        )

    def test_workflow_cannot_move_a_hard_rule_into_reviews(self) -> None:
        data = self.library.workflow("refund-request").model_dump(mode="json")
        disputed = next(item for item in data["rules"] if item["id"] == "no-refund-disputed-payment")
        data["rules"].remove(disputed)
        data["reviews"].append(disputed)

        with self.assertRaises(ValidationError):
            WorkflowSpec.model_validate(data)
