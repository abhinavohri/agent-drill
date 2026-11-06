import json
import shutil
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from evaluation_support import load_library
from pydantic import JsonValue, ValidationError

from app.jobs.build_refund_fixtures import LIBRARY_ROOT
from app.refunds.facade import (
    REFUND_TOOL_ARGUMENTS,
    RefundScenario,
    RefundToolProvider,
    RefundWorld,
)
from app.workflows.facade import (
    LibraryError,
    Scenario,
    ScenarioPattern,
    UnknownRecordError,
    WorkflowSpec,
    load_scenario_library,
)


@contextmanager
def edited_library(relative_path: str, **changes: JsonValue) -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "refunds"
        shutil.copytree(LIBRARY_ROOT, root)
        path = root / relative_path
        data = json.loads(path.read_text())
        data.update(changes)
        path.write_text(json.dumps(data))
        yield root


def world_for(scenario: Scenario) -> RefundWorld:
    return RefundWorld(
        RefundScenario(
            id=scenario.id,
            initial_state=scenario.initial_state,
            faults=list(scenario.faults),
        )
    )


class ScenarioLibraryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.library = load_library()

    def test_loads_refund_workflow_scenarios_and_scripts(self) -> None:
        self.assertEqual(set(self.library.workflows), {"refund-request"})
        self.assertEqual(
            {scenario.pattern for scenario in self.library.scenarios.values()},
            set(ScenarioPattern),
        )
        self.assertEqual(len(self.library.scripts), 2 * len(self.library.scenarios))

    def test_every_scenario_has_an_unsafe_run_and_a_safe_rerun(self) -> None:
        for scenario_id in self.library.scenarios:
            unsafe = self.library.script(f"{scenario_id}.unsafe")
            safe = self.library.script(f"{scenario_id}.safe")

            self.assertIsNone(unsafe.rerun_of)
            self.assertEqual(safe.rerun_of, unsafe.id)
            self.assertNotEqual(safe.agent_version, unsafe.agent_version)

    def test_scenarios_seed_refund_worlds(self) -> None:
        for scenario in self.library.scenarios.values():
            world = world_for(scenario)

            self.assertEqual(world.snapshot(), scenario.initial_state.model_dump(mode="json"))

    async def test_refund_tool_arguments_cover_the_refund_catalog(self) -> None:
        provider = RefundToolProvider(world_for(self.library.scenario("valid-refund")))

        tools = await provider.list_tools()

        self.assertEqual(set(REFUND_TOOL_ARGUMENTS), {tool.name for tool in tools})

    def test_reports_unknown_records(self) -> None:
        with self.assertRaises(UnknownRecordError):
            self.library.scenario("missing-scenario")

    def test_rejects_scenario_for_missing_workflow(self) -> None:
        with (
            edited_library("scenarios/valid-refund.json", workflow_id="other-workflow") as root,
            self.assertRaisesRegex(LibraryError, "missing record other-workflow"),
        ):
            load_scenario_library(root)

    def test_rejects_expected_outcome_outside_the_workflow(self) -> None:
        outcomes: JsonValue = ["refund_issued", "declined"]
        with (
            edited_library("workflows/refund-request.json", outcomes=outcomes) as root,
            self.assertRaisesRegex(LibraryError, "outside workflow refund-request: manual_review"),
        ):
            load_scenario_library(root)

    def test_rejects_workflow_tool_that_the_refund_world_lacks(self) -> None:
        workflow = json.loads((LIBRARY_ROOT / "workflows" / "refund-request.json").read_text())
        tools: JsonValue = [*workflow["tools"], {"name": "delete_account", "access": "write"}]
        with (
            edited_library("workflows/refund-request.json", tools=tools) as root,
            self.assertRaisesRegex(LibraryError, "unknown tools: delete_account"),
        ):
            load_scenario_library(root)

    def test_rejects_fault_for_undeclared_tool(self) -> None:
        faults: JsonValue = [
            {"tool": "charge_card", "kind": "error", "times": 1, "message": "Card failed"}
        ]
        with (
            edited_library("scenarios/payment-timeout.json", faults=faults) as root,
            self.assertRaisesRegex(LibraryError, "undeclared tools: charge_card"),
        ):
            load_scenario_library(root)

    def test_rejects_record_whose_id_does_not_match_its_file(self) -> None:
        with (
            edited_library("scenarios/valid-refund.json", id="renamed-refund") as root,
            self.assertRaisesRegex(LibraryError, "must contain id valid-refund"),
        ):
            load_scenario_library(root)

    def test_rejects_rerun_of_a_different_scenario(self) -> None:
        with (
            edited_library(
                "agent_scripts/valid-refund.safe.json",
                rerun_of="disputed-payment-750.unsafe",
            ) as root,
            self.assertRaisesRegex(LibraryError, "same scenario and agent"),
        ):
            load_scenario_library(root)

    def test_scenario_conversation_must_exist_in_the_seed_state(self) -> None:
        data = self.library.scenario("valid-refund").model_dump(mode="json")
        data["conversation_id"] = "conversation_9"

        with self.assertRaisesRegex(ValidationError, "conversation_9"):
            Scenario.model_validate(data)

    def test_workflow_rejects_duplicate_rule_ids(self) -> None:
        data = self.library.workflow("refund-request").model_dump(mode="json")
        data["rules"].append(dict(data["rules"][0]))

        with self.assertRaisesRegex(ValidationError, "Duplicate rule id"):
            WorkflowSpec.model_validate(data)

    def test_required_reads_must_be_read_tools(self) -> None:
        data = self.library.workflow("refund-request").model_dump(mode="json")
        data["rules"][0]["tools"] = ["get_payment", "create_refund"]

        with self.assertRaisesRegex(ValidationError, "undeclared tools: create_refund"):
            WorkflowSpec.model_validate(data)

    def test_retry_recheck_tools_must_be_read_tools(self) -> None:
        data = self.library.workflow("refund-request").model_dump(mode="json")
        retry = next(item for item in data["rules"] if item["kind"] == "recheck_before_refund_retry")
        retry["tools"] = ["create_refund"]

        with self.assertRaisesRegex(ValidationError, "undeclared tools: create_refund"):
            WorkflowSpec.model_validate(data)

    def test_workflow_cannot_list_no_resolution_as_valid(self) -> None:
        data = self.library.workflow("refund-request").model_dump(mode="json")
        data["outcomes"].append("no_resolution")

        with self.assertRaisesRegex(ValidationError, "no_resolution"):
            WorkflowSpec.model_validate(data)
