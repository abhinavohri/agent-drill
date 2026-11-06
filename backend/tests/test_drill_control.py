import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.drills.facade import CommandDrillRunner, CommandRunnerConfig, DrillRunStatus
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

            result = CommandDrillRunner(config).run("scenario-1")

        self.assertEqual(result.status, DrillRunStatus.COMPLETED)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "target ran\n")
        self.assertEqual(result.agent_name, "shopping-agent")
        self.assertEqual(result.agent_version, "fixture-v1")

    def test_passes_scenario_as_command_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(TRACE_FIXTURE, root / "trace.json")
            command = (sys.executable, "-c", "import sys; print(sys.argv[1])", "{scenario_id}")

            result = CommandDrillRunner(self._config(root, command)).run("scenario-2")

        self.assertEqual(result.status, DrillRunStatus.COMPLETED)
        self.assertEqual(result.stdout, "scenario-2\n")

    def test_reports_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = (sys.executable, "-c", "import sys; sys.exit(3)")

            result = CommandDrillRunner(self._config(root, command)).run("scenario-3")

        self.assertEqual(result.status, DrillRunStatus.FAILED)
        self.assertEqual(result.exit_code, 3)
        self.assertIn("exited with code 3", result.error)

    def test_reports_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = (sys.executable, "-c", "import time; time.sleep(1)")
            config = self._config(root, command, timeout_seconds=0.01)

            result = CommandDrillRunner(config).run("scenario-4")

        self.assertEqual(result.status, DrillRunStatus.TIMED_OUT)
        self.assertIsNone(result.exit_code)
        self.assertIn("exceeded", result.error)

    def test_reports_missing_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root, (sys.executable, "-c", "pass"))

            result = CommandDrillRunner(config).run("scenario-5")

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
                result = CommandDrillRunner(self._config(root, command)).run("scenario-safe")

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
                        "command": [sys.executable, "-c", "print('target ran')"],
                        "working_directory": ".",
                        "timeout_seconds": 5,
                        "trace_path": "trace.json",
                    }
                )
            )

            exit_code = main(
                [str(config_path), "scenario-6", "--output", str(result_path)]
            )

            result = json.loads(result_path.read_text())
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "completed")
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
