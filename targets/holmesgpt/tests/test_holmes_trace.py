import unittest

from atif import Trajectory
from pydantic import ValidationError

from holmes_trace import HolmesResult, trajectory_from_holmes
from run_target import HOST_TOOLSETS, holmes_config

ANSWER = {
    "messages": [
        {"role": "system", "content": "You are HolmesGPT."},
        {"role": "user", "content": "A customer is waiting in support conversation conversation_1."},
        {
            "role": "assistant",
            "content": None,
            "reasoning_content": "Read the order and payment first.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_order", "arguments": '{"orderId": "order_1"}'},
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "get_payment", "arguments": '{"paymentId": "payment_1"}'},
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_2", "name": "get_payment", "content": "payment output"},
        {"role": "tool", "tool_call_id": "call_1", "name": "get_order", "content": "order output"},
        {"role": "assistant", "content": [{"type": "text", "text": "I escalated the refund."}]},
    ],
    "prompt_tokens": 1200,
    "completion_tokens": 80,
    "cached_tokens": 600,
    "total_cost": 0.0012,
    "num_llm_calls": 2,
    "result": "I escalated the refund.",
}


class HolmesTraceTests(unittest.TestCase):
    def test_converts_holmes_messages_to_atif_steps(self) -> None:
        trajectory = trajectory_from_holmes(
            HolmesResult.model_validate(ANSWER),
            "0.46.0+claude-haiku-5-5",
            "anthropic/claude-haiku-5-5",
        )

        self.assertEqual([step.source for step in trajectory.steps], ["system", "user", "agent", "agent"])
        tool_step = trajectory.steps[2]
        self.assertEqual(
            [(call.function_name, call.arguments) for call in tool_step.tool_calls],
            [("get_order", {"orderId": "order_1"}), ("get_payment", {"paymentId": "payment_1"})],
        )
        self.assertEqual(
            [(result.source_call_id, result.content) for result in tool_step.observation.results],
            [("call_1", "order output"), ("call_2", "payment output")],
        )
        self.assertEqual(tool_step.reasoning_content, "Read the order and payment first.")
        self.assertEqual(trajectory.steps[3].message, "I escalated the refund.")
        self.assertEqual(trajectory.agent.version, "0.46.0+claude-haiku-5-5")
        self.assertEqual(trajectory.final_metrics.total_prompt_tokens, 1200)
        self.assertEqual(trajectory.final_metrics.total_steps, 4)
        Trajectory.model_validate(trajectory.model_dump())

    def test_leaves_missing_tool_output_empty(self) -> None:
        answer = {"messages": ANSWER["messages"][:3]}

        trajectory = trajectory_from_holmes(HolmesResult.model_validate(answer), "v", "model")

        self.assertEqual(
            [result.content for result in trajectory.steps[2].observation.results],
            [None, None],
        )

    def test_rejects_tool_arguments_that_are_not_a_json_object(self) -> None:
        for arguments in ("not json", "[1, 2]"):
            call = {"id": "call_1", "function": {"name": "get_order", "arguments": arguments}}
            answer = {"messages": [{"role": "assistant", "tool_calls": [call]}]}
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                HolmesResult.model_validate(answer)

    def test_config_points_at_drill_server_and_disables_host_toolsets(self) -> None:
        config = holmes_config("http://127.0.0.1:8000/mcp")

        self.assertIn('url: "http://127.0.0.1:8000/mcp"', config)
        self.assertIn("mode: streamable-http", config)
        for name in HOST_TOOLSETS:
            self.assertIn(f"  {name}:\n    enabled: false\n", config)
