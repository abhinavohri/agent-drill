from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.simulations.facade import SimulationRun
from app.workflows.facade import Outcome, TeamRole


class EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"


class CheckName(StrEnum):
    INPUT_SCHEMA = "input_schema"
    TOOL_PERMISSIONS = "tool_permissions"
    ACTION_ORDER = "action_order"
    FINAL_STATE = "final_state"
    SEMANTIC_OUTPUT = "semantic_output"
    HUMAN_APPROVAL = "human_approval"


class Tier(StrEnum):
    HARD = "hard"
    REVIEW = "review"


class ResultStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    OPEN = "open"
    SKIPPED = "skipped"


class ActionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    NO_OUTCOME = "no_outcome"


class Decision(StrEnum):
    APPROVE = "approve"
    BLOCK = "block"


class Evidence(EvaluationModel):
    event_sequences: tuple[int, ...] = ()
    state_paths: tuple[str, ...] = ()


class RuleResult(EvaluationModel):
    rule_id: str
    check: CheckName
    owner: TeamRole
    policy: str
    status: ResultStatus
    message: str
    evidence: Evidence = Field(default_factory=Evidence)


class CheckResult(EvaluationModel):
    check: CheckName
    tier: Tier
    status: ResultStatus
    rules: tuple[RuleResult, ...]


class ActionSummary(EvaluationModel):
    sequence: int
    tool: str
    arguments: dict[str, JsonValue]
    status: ActionStatus


class RunMetrics(EvaluationModel):
    duration_ms: int = Field(ge=0)
    total_prompt_tokens: int | None = Field(default=None, ge=0)
    total_completion_tokens: int | None = Field(default=None, ge=0)
    total_cached_tokens: int | None = Field(default=None, ge=0)
    total_cost_usd: float | None = Field(default=None, ge=0)
    total_steps: int | None = Field(default=None, ge=0)
    llm_calls: int | None = Field(default=None, ge=0)


class RunResult(EvaluationModel):
    run_id: str
    agent_id: str
    agent_version: str
    workflow_id: str
    scenario_id: str
    verdict: Verdict
    outcome: Outcome | None
    expected_outcomes: tuple[Outcome, ...]
    pending_approvals: tuple[TeamRole, ...]
    checks: tuple[CheckResult, ...]
    actions: tuple[ActionSummary, ...]
    metrics: RunMetrics | None = None

    def rules_with_status(self, status: ResultStatus) -> tuple[RuleResult, ...]:
        return tuple(rule for check in self.checks for rule in check.rules if rule.status is status)

    def failed_rules(self) -> tuple[RuleResult, ...]:
        return self.rules_with_status(ResultStatus.FAILED)


class ReviewDecision(EvaluationModel):
    reviewer: str = Field(min_length=1)
    role: TeamRole
    decision: Decision


class JudgeAssessment(EvaluationModel):
    judge: str = Field(min_length=1)
    acceptable: bool
    note: str = Field(min_length=1)


class ReviewInput(EvaluationModel):
    decisions: tuple[ReviewDecision, ...] = ()
    judge_assessments: tuple[JudgeAssessment, ...] = ()


class RecordedRun(EvaluationModel):
    agent_id: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    run: SimulationRun


class RuleChange(EvaluationModel):
    rule_id: str
    before: ResultStatus
    after: ResultStatus


class ComparedRun(EvaluationModel):
    run_id: str
    agent_version: str
    verdict: Verdict
    outcome: Outcome | None
    tools: tuple[str, ...]
    metrics: RunMetrics | None


class RunComparison(EvaluationModel):
    agent_id: str
    workflow_id: str
    scenario_id: str
    original: ComparedRun
    rerun: ComparedRun
    rule_changes: tuple[RuleChange, ...]
