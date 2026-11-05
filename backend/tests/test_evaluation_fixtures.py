import json
import re
import unittest
from pathlib import Path

from evaluation_support import evaluate, load_library, rule, saved_run

from app.evaluations.facade import RecordedRun, ResultStatus, ReviewInput, RunResult, Verdict
from app.jobs.build_refund_fixtures import LIBRARY_ROOT, fixture_outputs, record_script
from app.simulations.facade import CompletedRun, RunEvent

STUB_ROOT = Path(__file__).parents[1] / "fixtures" / "stubs"
SENSITIVE_PATTERNS = {
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "card number": re.compile(r"\b\d{13,19}\b"),
    "phone number": re.compile(r"\+?\b\d{3}[ .-]\d{3}[ .-]\d{4}\b"),
    "API key": re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test)?[-_]?[A-Za-z0-9]{12,}"),
    "bearer token": re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{10,}"),
    "credential field": re.compile(r"(?i)\b(?:api[_-]?key|password|secret|access[_-]?token)\b"),
}


class SavedFixtureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.library = load_library()
        self.runs = {script_id: saved_run(script_id) for script_id in self.library.scripts}

    def test_saved_results_have_the_expected_verdicts(self) -> None:
        verdicts = {
            script_id: RunResult.model_validate_json(
                (LIBRARY_ROOT / "results" / f"{script_id}.json").read_text()
            ).verdict
            for script_id in self.library.scripts
        }

        expected = {
            script_id: Verdict.FAIL if script_id.endswith(".unsafe") else Verdict.PASS
            for script_id in self.library.scripts
        }
        self.assertEqual(verdicts, expected)

    def test_saved_results_and_reports_match_the_saved_runs(self) -> None:
        outputs = fixture_outputs(self.library, LIBRARY_ROOT, self.runs)

        stale = [
            str(path.relative_to(LIBRARY_ROOT))
            for path, content in outputs.items()
            if not path.exists() or path.read_text() != content
        ]
        self.assertEqual(stale, [])

    async def test_agent_scripts_replay_to_the_saved_runs(self) -> None:
        for script in self.library.scripts.values():
            with self.subTest(script=script.id):
                replayed = await record_script(script, self.library.scenario(script.scenario_id))
                saved = self.runs[script.id]

                self.assertIsInstance(replayed.run, CompletedRun)
                self.assertIsInstance(saved.run, CompletedRun)
                self.assertEqual(
                    [event.type for event in replayed.run.events],
                    [event.type for event in saved.run.events],
                )
                self.assertEqual(
                    [event.payload for event in replayed.run.events],
                    [event.payload for event in saved.run.events],
                )
                self.assertEqual(replayed.run.model_dump()["final_state"], saved.run.model_dump()["final_state"])

    def test_simulation_handoff_stub_fails_deterministically(self) -> None:
        events = tuple(
            RunEvent.model_validate(value)
            for value in json.loads((STUB_ROOT / "run-events.json").read_text())
        )
        run = CompletedRun(
            id="stub-handoff",
            scenario_id="disputed-payment-750",
            sandbox_id="stub-sandbox",
            action_count=2,
            max_actions=20,
            events=events,
            final_state=json.loads((STUB_ROOT / "final-state.json").read_text()),
        )
        handoff = RecordedRun(
            agent_id="refund-agent",
            agent_version="fixture-v1",
            workflow_id="refund-request",
            run=run,
        )
        scenario = self.library.scenario("disputed-payment-750")

        first = evaluate(self.library, scenario, handoff, ReviewInput())
        second = evaluate(self.library, scenario, handoff, ReviewInput())

        disputed = rule(first, "no-refund-disputed-payment")
        self.assertEqual(first, second)
        self.assertEqual(first.verdict, Verdict.FAIL)
        self.assertEqual(disputed.status, ResultStatus.FAILED)
        self.assertEqual(disputed.evidence.event_sequences[0], 4)

    def test_fixtures_contain_no_secrets_or_customer_data(self) -> None:
        findings = [
            f"{path.relative_to(LIBRARY_ROOT)}: {label}"
            for path in sorted(LIBRARY_ROOT.rglob("*"))
            if path.suffix in {".json", ".md"}
            for label, pattern in SENSITIVE_PATTERNS.items()
            if pattern.search(path.read_text())
        ]

        self.assertEqual(findings, [])

    def test_scenarios_use_synthetic_customers(self) -> None:
        customer_ids = {
            record.customer_id
            for scenario in self.library.scenarios.values()
            for record in (
                *scenario.initial_state.conversations.values(),
                *scenario.initial_state.orders.values(),
            )
        }

        self.assertTrue(all(value.startswith("customer_fixture_") for value in customer_ids))
