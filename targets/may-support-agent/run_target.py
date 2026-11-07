import argparse
import sys
from pathlib import Path
from time import monotonic

from atif import Agent, FinalMetrics, Step, Trajectory
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ATIF_VERSION = "ATIF-v1.7"
AGENT_NAME = "may-support-triage"
AGENT_VERSION = "may26-local"


class AdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SupportTask(AdapterModel):
    issue: str = Field(min_length=1)
    subject: str = ""
    company: str = "None"


class AgentResult(AdapterModel):
    response: str
    product_area: str
    status: str
    request_type: str
    justification: str


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    started = monotonic()
    try:
        task = _parse_task(args.task)
        result, model = _run_agent(task, args.agent_root.resolve())
        trajectory = _trajectory(args.scenario_id, args.task, result, model, started)
        args.trace.parent.mkdir(parents=True, exist_ok=True)
        args.trace.write_text(trajectory.model_dump_json(indent=2, exclude_none=True) + "\n")
    except (OSError, ValidationError, ValueError) as exc:
        sys.stderr.write(f"Cannot run the May support agent: {exc}\n")
        return 1
    sys.stdout.write(result.model_dump_json() + "\n")
    return 0


def _parse_task(value: str) -> SupportTask:
    if not value.lstrip().startswith("{"):
        return SupportTask(issue=value)
    return SupportTask.model_validate_json(value)


def _run_agent(task: SupportTask, agent_root: Path) -> tuple[AgentResult, str]:
    code_root = agent_root / "code"
    if not code_root.is_dir():
        raise ValueError(f"May agent code directory does not exist: {code_root}")
    sys.path.insert(0, str(code_root))

    from config import LLM_MODEL
    from models.schemas import Ticket
    from pipeline.orchestrator import PipelineOrchestrator
    from services.embedding import LocalEmbeddingService
    from services.escalation import RuleBasedEscalation
    from services.llm import GeminiLLMService
    from services.retrieval import CosineRetriever
    from services.vector_store import LocalVectorStore

    store = LocalVectorStore()
    try:
        if store.get_article_count() == 0:
            raise ValueError("May support corpus is not indexed")
        orchestrator = PipelineOrchestrator(
            retrieval_service=CosineRetriever(LocalEmbeddingService(), store),
            escalation_service=RuleBasedEscalation(),
            llm_service=GeminiLLMService(),
        )
        output = orchestrator.process_ticket(
            Ticket(issue=task.issue, subject=task.subject, company=task.company)
        )
    finally:
        store.close()
    return AgentResult.model_validate(output, from_attributes=True), LLM_MODEL


def _trajectory(
    scenario_id: str,
    raw_task: str,
    result: AgentResult,
    model: str,
    started: float,
) -> Trajectory:
    return Trajectory(
        schema_version=ATIF_VERSION,
        session_id=scenario_id,
        agent=Agent(name=AGENT_NAME, version=AGENT_VERSION, model_name=model),
        steps=[
            Step(step_id=1, source="user", message=raw_task),
            Step(
                step_id=2,
                source="agent",
                model_name=model,
                message=result.response,
                llm_call_count=1,
                extra={
                    "status": result.status,
                    "request_type": result.request_type,
                    "product_area": result.product_area,
                    "justification": result.justification,
                },
            ),
        ],
        final_metrics=FinalMetrics(
            total_steps=2,
            extra={"llm_calls": 1, "duration_ms": int((monotonic() - started) * 1000)},
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the May support agent and write an ATIF trace."
    )
    parser.add_argument("--agent-root", type=Path, required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--trace", type=Path, required=True)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
