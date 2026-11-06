import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from app.drills.facade import DrillRun, DrillRunStatus
from app.evaluations.facade import RecordedRun, RunResult
from app.jobs.run_refund_drill import LIBRARY_ROOT, UNIDENTIFIED_AGENT, main
from app.simulations.facade import RunEventType
from app.workflows.facade import load_scenario_library

TRACE_FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "production_traces" / "shopping-agent.atif.json"
)
MCP_TARGET = """
import asyncio
import shutil
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def call(name, arguments):
    async with streamablehttp_client(sys.argv[1]) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(name, arguments)


async def main():
    await call("get_conversation", {"conversationId": sys.argv[2]})
    await call("get_refund_history", {"paymentId": "payment_1"})


asyncio.run(main())
shutil.copy(sys.argv[3], sys.argv[4])
"""


class RefundDrillJobTests(unittest.TestCase):
    def test_serves_scenario_to_target_and_grades_its_run(self) -> None:
        command = [
            sys.executable,
            "-c",
            MCP_TARGET,
            "{mcp_url}",
            "{conversation_id}",
            str(TRACE_FIXTURE),
            "{output_dir}/trajectory.json",
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            exit_code, stdout = self._run(Path(directory), command, output)
            recorded = RecordedRun.model_validate_json((output / "recorded-run.json").read_text())
            result = RunResult.model_validate_json((output / "result.json").read_text())
            policy = (output / "policy.md").read_text()
            report_written = (output / "report.md").exists()

        calls = [
            (event.payload.tool, event.payload.arguments)
            for event in recorded.run.events
            if event.type is RunEventType.TOOL_CALL
        ]
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            calls,
            [
                ("get_conversation", {"conversationId": "conversation_1"}),
                ("get_refund_history", {"paymentId": "payment_1"}),
            ],
        )
        self.assertEqual((recorded.agent_id, recorded.agent_version), ("shopping-agent", "fixture-v1"))
        self.assertEqual(result.scenario_id, "valid-refund")
        self.assertTrue(report_written)
        self.assertIn("valid-refund: target completed", stdout)
        workflow = load_scenario_library(LIBRARY_ROOT).workflow("refund-request")
        for rule in workflow.rules:
            self.assertIn(f"- {rule.policy}\n", policy)

    def test_grades_run_when_target_fails(self) -> None:
        command = [sys.executable, "-c", "import sys; sys.exit(3)"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            exit_code, _ = self._run(Path(directory), command, output)
            drill = DrillRun.model_validate_json((output / "drill-run.json").read_text())
            recorded = RecordedRun.model_validate_json((output / "recorded-run.json").read_text())
            result_written = (output / "result.json").exists()

        self.assertEqual(exit_code, 1)
        self.assertEqual(drill.status, DrillRunStatus.FAILED)
        self.assertEqual(recorded.agent_id, UNIDENTIFIED_AGENT)
        self.assertTrue(result_written)

    @staticmethod
    def _run(root: Path, command: list[str], output: Path) -> tuple[int, str]:
        config = root / "drill.json"
        config.write_text(
            json.dumps(
                {
                    "kind": "command",
                    "command": command,
                    "working_directory": str(root),
                    "inherit_environment": ["PATH"],
                    "environment": {},
                    "timeout_seconds": 60,
                    "trace_path": "{output_dir}/trajectory.json",
                }
            )
        )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main([str(config), "valid-refund", "--output", str(output)])
        return exit_code, stdout.getvalue()
