from app.evaluations.facade import RecordedRun, ReviewInput, RuleResult, RunResult, evaluate_run
from app.jobs.build_refund_fixtures import LIBRARY_ROOT, record_script
from app.simulations.facade import SimulationRun
from app.workflows.facade import (
    AgentScript,
    Scenario,
    ScenarioLibrary,
    ScriptedCall,
    load_scenario_library,
)

AGENT_ID = "refund-agent"
WORKFLOW_ID = "refund-request"


def load_library() -> ScenarioLibrary:
    return load_scenario_library(LIBRARY_ROOT)


def call(tool: str, **arguments: str | int) -> ScriptedCall:
    return ScriptedCall(tool=tool, arguments=dict(arguments))


def reads(*, order_id: str = "order_1", payment_id: str = "payment_1") -> tuple[ScriptedCall, ...]:
    return (
        call("get_conversation", conversationId="conversation_1"),
        call("get_order", orderId=order_id),
        call("get_payment", paymentId=payment_id),
    )


async def play(scenario: Scenario, *calls: ScriptedCall) -> RecordedRun:
    script = AgentScript(
        id="test-run",
        scenario_id=scenario.id,
        agent_id=AGENT_ID,
        agent_version="test",
        calls=calls,
    )
    return await record_script(script, scenario)


def recorded(run: SimulationRun) -> RecordedRun:
    return RecordedRun(agent_id=AGENT_ID, agent_version="test", workflow_id=WORKFLOW_ID, run=run)


def evaluate(
    library: ScenarioLibrary,
    scenario: Scenario,
    run: RecordedRun,
    review: ReviewInput,
) -> RunResult:
    return evaluate_run(library.workflow(scenario.workflow_id), scenario, run, review)


def saved_run(script_id: str) -> RecordedRun:
    return RecordedRun.model_validate_json((LIBRARY_ROOT / "runs" / f"{script_id}.json").read_text())


def rule(result: RunResult, rule_id: str) -> RuleResult:
    return next(item for check in result.checks for item in check.rules if item.rule_id == rule_id)
