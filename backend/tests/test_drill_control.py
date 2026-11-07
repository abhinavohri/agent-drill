import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.drills.facade import (
    CommandDrillRunner,
    CommandRunnerConfig,
    DrillRunStatus,
    TargetRunContext,
)
from app.jobs.run_drill import main
from app.traces.facade import load_atif

TRACE_FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "production_traces" / "shopping-agent.atif.json"
)


class DrillControlTests(unittest.TestCase):
    def test_runs_command_and_reads_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(TRACE_FIXTURE, root / "trace.json")
            config = self._config(root, (sys.executable, "-c", "print('target ran')"))

            result = CommandDrillRunner(config).run(TargetRunContext(scenario_id="scenario-1"))

        self.assertEqual(result.status, DrillRunStatus.COMPLETED)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "target ran\n")
        self.assertEqual(result.agent_name, "shopping-agent")
        self.assertEqual(result.agent_version, "fixture-v1")

    def test_supplies_the_stable_adapter_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(TRACE_FIXTURE, root / "trace.json")
            policy = root / "policy.md"
            command = (
                sys.executable,
                "-c",
                "import sys; print('|'.join(sys.argv[1:]))",
                "{scenario_id}",
                "{task}",
                "{mcp_url}",
                "{trace_path}",
                "{output_dir}",
                "{policy_file}",
            )
            context = TargetRunContext(
                scenario_id="scenario-2",
                task="Resolve the request.",
                mcp_url="http://127.0.0.1:8000/mcp",
                trace_path=root / "trace.json",
                policy_file=policy,
            )

            result = CommandDrillRunner(self._config(root, command)).run(context)

        self.assertEqual(result.status, DrillRunStatus.COMPLETED)
        resolved_root = root.resolve()
        self.assertEqual(
            result.stdout,
            (
                f"scenario-2|Resolve the request.|http://127.0.0.1:8000/mcp|"
                f"{resolved_root / 'trace.json'}|{resolved_root}|{policy.resolve()}\n"
            ),
        )

    def test_reports_a_missing_adapter_value_before_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = (sys.executable, "-c", "pass", "{mcp_url}")

            result = CommandDrillRunner(self._config(root, command)).run(
                TargetRunContext(scenario_id="scenario-missing")
            )

        self.assertEqual(result.status, DrillRunStatus.FAILED)
        self.assertIn("requires {mcp_url}", result.error)

    def test_rejects_an_unknown_adapter_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValidationError):
            self._config(Path(directory), (sys.executable, "{unknown_value}"))

    def test_reports_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = (sys.executable, "-c", "import sys; sys.exit(3)")

            result = CommandDrillRunner(self._config(root, command)).run(
                TargetRunContext(scenario_id="scenario-3")
            )

        self.assertEqual(result.status, DrillRunStatus.FAILED)
        self.assertEqual(result.exit_code, 3)
        self.assertIn("exited with code 3", result.error)

    def test_reports_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = (sys.executable, "-c", "import time; time.sleep(1)")
            config = self._config(root, command, timeout_seconds=0.01)

            result = CommandDrillRunner(config).run(TargetRunContext(scenario_id="scenario-4"))

        self.assertEqual(result.status, DrillRunStatus.TIMED_OUT)
        self.assertIsNone(result.exit_code)
        self.assertIn("exceeded", result.error)

    def test_reports_missing_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root, (sys.executable, "-c", "pass"))

            result = CommandDrillRunner(config).run(TargetRunContext(scenario_id="scenario-5"))

        self.assertEqual(result.status, DrillRunStatus.FAILED)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cannot read", result.error)

    def test_does_not_inherit_unlisted_environment_variables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(TRACE_FIXTURE, root / "trace.json")
            command = (
                sys.executable,
                "-c",
                "import os; print(os.getenv('AGENT_DRILL_TEST_SECRET'))",
            )
            with patch.dict("os.environ", {"AGENT_DRILL_TEST_SECRET": "hidden"}):
                result = CommandDrillRunner(self._config(root, command)).run(
                    TargetRunContext(scenario_id="scenario-safe")
                )

        self.assertEqual(result.status, DrillRunStatus.COMPLETED)
        self.assertEqual(result.stdout, "None\n")

    def test_command_uses_relative_configuration_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(TRACE_FIXTURE, root / "trace.json")
            config_path = root / "drill.json"
            result_path = root / "result.json"
            config_path.write_text(
                json.dumps(
                    {
                        "kind": "command",
                        "command": [
                            sys.executable,
                            "-c",
                            "import sys; print(sys.argv[1])",
                            "{task}",
                        ],
                        "working_directory": ".",
                        "timeout_seconds": 5,
                        "trace_path": "trace.json",
                    }
                )
            )

            exit_code = main(
                [
                    str(config_path),
                    "scenario-6",
                    "--task",
                    "Resolve the request.",
                    "--output",
                    str(result_path),
                ]
            )

            result = json.loads(result_path.read_text())
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["stdout"], "Resolve the request.\n")
            self.assertEqual(
                load_atif(Path(result["trace_path"])).agent.name,
                "shopping-agent",
            )

    @staticmethod
    def _config(
        root: Path,
        command: tuple[str, ...],
        *,
        timeout_seconds: float = 5,
    ) -> CommandRunnerConfig:
        return CommandRunnerConfig(
            command=command,
            working_directory=root,
            timeout_seconds=timeout_seconds,
            trace_path=Path("trace.json"),
        )
