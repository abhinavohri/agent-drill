import json
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.jobs.run_ad_hoc_drill import main
from app.refunds.facade import RefundScenarioSeed, prepare_refund_scenario

TRACE_FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "production_traces" / "shopping-agent.atif.json"
)


class AdHocDrillTests(unittest.TestCase):
    def test_builds_consistent_refund_state_without_scripted_messages(self) -> None:
        prepared = prepare_refund_scenario(
            "double-charge",
            RefundScenarioSeed(
                order_total_cents=12500,
                delivery_status="delivered",
                payment_status="captured",
                prior_refund_cents=2500,
            ),
        )

        state = prepared.scenario.initial_state
        conversation = state.conversations[prepared.conversation_id]
        order = state.orders[conversation.order_id]
        payment = state.payments[order.payment_id]
        self.assertEqual(conversation.messages, [])
        self.assertEqual(order.customer_id, conversation.customer_id)
        self.assertEqual(payment.order_id, order.id)
        self.assertEqual(state.refunds[0].payment_id, payment.id)

    def test_rejects_a_prior_refund_above_the_payment(self) -> None:
        with self.assertRaisesRegex(ValidationError, "cannot exceed"):
            RefundScenarioSeed(
                order_total_cents=1000,
                delivery_status="delivered",
                payment_status="captured",
                prior_refund_cents=1001,
            )

    def test_runs_a_direct_scenario_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenario = root / "scenario.json"
            config = self._write_copy_config(root)
            output = root / "run"
            scenario.write_text(
                json.dumps(
                    {
                        "id": "custom-ticket",
                        "task": "Resolve this support request.",
                        "environment": {"kind": "direct"},
                    }
                )
            )
            exit_code = main([str(config), str(scenario), "--output", str(output)])

            result = json.loads((output / "drill-run.json").read_text())
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["stdout"], "Resolve this support request.\n")
            self.assertTrue((output / "trajectory.json").is_file())
            self.assertIn("Agent response", (output / "report.md").read_text())

    def test_runs_a_refund_scenario_with_generated_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenario = root / "scenario.json"
            config = self._write_copy_config(root)
            output = root / "run"
            scenario.write_text(
                json.dumps(
                    {
                        "id": "new-refund",
                        "task": "Resolve the refund request.",
                        "environment": {
                            "kind": "refund",
                            "order_total_cents": 4500,
                            "delivery_status": "delivered",
                            "payment_status": "captured",
                        },
                    }
                )
            )

            exit_code = main([str(config), str(scenario), "--output", str(output)])

            simulation = json.loads((output / "simulation-run.json").read_text())
            self.assertEqual(exit_code, 0)
            self.assertEqual(simulation["status"], "completed")
            self.assertEqual(simulation["action_count"], 0)
            conversations = simulation["final_state"]["conversations"]
            self.assertEqual(conversations["conversation-new-refund"]["messages"], [])

    @staticmethod
    def _write_copy_config(root: Path) -> Path:
        config = root / "drill.json"
        config.write_text(
            json.dumps(
                {
                    "kind": "command",
                    "command": [
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path; import shutil,sys; "
                            "dst=Path(sys.argv[2]); dst.parent.mkdir(parents=True,exist_ok=True); "
                            "shutil.copy(sys.argv[1],dst); print(sys.argv[3])"
                        ),
                        str(TRACE_FIXTURE),
                        "{trace_path}",
                        "{task}",
                    ],
                    "working_directory": str(root),
                    "timeout_seconds": 5,
                    "trace_path": "unused.json",
                }
            )
        )
        return config


if __name__ == "__main__":
    unittest.main()
