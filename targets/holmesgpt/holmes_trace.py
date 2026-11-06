import json
from typing import Literal

from atif import Agent, FinalMetrics, Observation, ObservationResult, Step, ToolCall, Trajectory
from pydantic import BaseModel, ConfigDict, field_validator

ATIF_VERSION = "ATIF-v1.7"
AGENT_NAME = "holmesgpt"


class HolmesModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class MessagePart(HolmesModel):
    type: str
    text: str = ""


class FunctionCall(HolmesModel):
    name: str
    arguments: dict[str, object]

    @field_validator("arguments", mode="before")
    @classmethod
    def decode_arguments(cls, value: object) -> object:
        return json.loads(value) if isinstance(value, str) else value


class HolmesToolCall(HolmesModel):
    id: str
    function: FunctionCall


class HolmesMessage(HolmesModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | tuple[MessagePart, ...] | None = None
    tool_calls: tuple[HolmesToolCall, ...] | None = None
    tool_call_id: str | None = None
    reasoning_content: str | None = None

    @property
    def text(self) -> str:
        if self.content is None:
            return ""
        if isinstance(self.content, str):
            return self.content
        return "\n".join(part.text for part in self.content if part.type == "text")


class HolmesResult(HolmesModel):
    messages: tuple[HolmesMessage, ...]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int | None = None
    total_cost: float = 0.0
    num_llm_calls: int | None = None


def trajectory_from_holmes(result: HolmesResult, agent_version: str, model: str) -> Trajectory:
    outputs = {
        message.tool_call_id: message.text
        for message in result.messages
        if message.role == "tool" and message.tool_call_id is not None
    }
    steps: list[Step] = []
    for message in result.messages:
        step_id = len(steps) + 1
        if message.role == "assistant":
            steps.append(_agent_step(step_id, message, outputs, model))
        elif message.role != "tool":
            steps.append(Step(step_id=step_id, source=message.role, message=message.text))
    return Trajectory(
        schema_version=ATIF_VERSION,
        agent=Agent(name=AGENT_NAME, version=agent_version, model_name=model),
        steps=steps,
        final_metrics=FinalMetrics(
            total_prompt_tokens=result.prompt_tokens,
            total_completion_tokens=result.completion_tokens,
            total_cached_tokens=result.cached_tokens,
            total_cost_usd=result.total_cost,
            total_steps=len(steps),
            extra={"llm_calls": result.num_llm_calls},
        ),
    )


def _agent_step(step_id: int, message: HolmesMessage, outputs: dict[str, str], model: str) -> Step:
    calls = message.tool_calls or ()
    return Step(
        step_id=step_id,
        source="agent",
        model_name=model,
        message=message.text,
        reasoning_content=message.reasoning_content or None,
        tool_calls=[
            ToolCall(
                tool_call_id=call.id,
                function_name=call.function.name,
                arguments=call.function.arguments,
            )
            for call in calls
        ]
        or None,
        observation=Observation(
            results=[
                ObservationResult(source_call_id=call.id, content=outputs.get(call.id))
                for call in calls
            ]
        )
        if calls
        else None,
    )
