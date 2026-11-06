import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from app.jobs.ingest_trace import main
from app.traces.facade import TraceInputError, load_atif, parse_atif

FIXTURE = Path(__file__).parents[1] / "fixtures" / "production_traces" / "shopping-agent.atif.json"


class TraceIngestionTests(unittest.TestCase):
    def test_loads_atif_trajectory(self) -> None:
        trajectory = load_atif(FIXTURE)

        self.assertEqual(trajectory.schema_version, "ATIF-v1.7")
        self.assertEqual(trajectory.agent.name, "shopping-agent")
        self.assertEqual(trajectory.steps[1].tool_calls[0].function_name, "search_products")
        self.assertEqual(
            trajectory.steps[1].observation.results[0].source_call_id,
            "call_search_1",
        )

    def test_rejects_nonsequential_steps(self) -> None:
        data = json.loads(FIXTURE.read_text())
        data["steps"][1]["step_id"] = 3

        with self.assertRaisesRegex(TraceInputError, "not sequential"):
            parse_atif(json.dumps(data))

    def test_rejects_unsupported_version(self) -> None:
        data = json.loads(FIXTURE.read_text())
        data["schema_version"] = "ATIF-v1.8"

        with self.assertRaisesRegex(TraceInputError, "Unsupported ATIF schema version"):
            parse_atif(json.dumps(data))

    def test_rejects_nonobject_json(self) -> None:
        with self.assertRaisesRegex(TraceInputError, "root value must be an object"):
            parse_atif("[]")

    def test_command_writes_normalized_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "normalized.json"

            self.assertEqual(main([str(FIXTURE), "--output", str(output)]), 0)
            self.assertEqual(load_atif(output), load_atif(FIXTURE))

    def test_command_writes_to_standard_output(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            self.assertEqual(main([str(FIXTURE)]), 0)

        self.assertEqual(parse_atif(output.getvalue()), load_atif(FIXTURE))
