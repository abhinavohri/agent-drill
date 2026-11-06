from collections.abc import Collection, Iterable
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.refunds.facade import RefundState, ToolFault

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")]


class LibraryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LibraryRecord(LibraryModel):
    id: Identifier


class Outcome(StrEnum):
    REFUND_ISSUED = "refund_issued"
    MANUAL_REVIEW = "manual_review"
    DECLINED = "declined"
    NO_RESOLUTION = "no_resolution"


class TeamRole(StrEnum):
    SUPPORT = "support"
    FINANCE = "finance"
    SECURITY = "security"
    ENGINEERING = "engineering"


class ToolAccess(StrEnum):
    READ = "read"
    WRITE = "write"


class ScenarioPattern(StrEnum):
    VALID = "valid"
    DISPUTED = "disputed"
    DUPLICATE = "duplicate"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    CONFLICTING_DATA = "conflicting_data"
    REPEATED_ACTION = "repeated_action"
    PROMPT_INJECTION = "prompt_injection"
    MISSING_APPROVAL = "missing_approval"


class WorkflowTool(LibraryModel):
    name: str = Field(min_length=1)
    access: ToolAccess


class WorkflowStage(LibraryModel):
    id: Identifier
    title: str = Field(min_length=1)
    tools: tuple[str, ...] = Field(min_length=1)


class RuleSpec(LibraryModel):
    id: Identifier
    policy: str = Field(min_length=1)
    owner: TeamRole


class RequiredReadsRule(RuleSpec):
    kind: Literal["required_reads_before_refund"]
    tools: tuple[str, ...] = Field(min_length=1)


class DisputedPaymentRule(RuleSpec):
    kind: Literal["no_refund_for_disputed_payment"]


class DuplicateRefundRule(RuleSpec):
    kind: Literal["no_duplicate_refund"]


class RefundLimitRule(RuleSpec):
    kind: Literal["refund_approval_limit"]
    limit_cents: int = Field(gt=0)


class CustomerOrderRule(RuleSpec):
    kind: Literal["refund_only_customer_orders"]


class DeliveredOrderRule(RuleSpec):
    kind: Literal["refund_only_delivered_orders"]


class RefundRetryRule(RuleSpec):
    kind: Literal["recheck_before_refund_retry"]
    tools: tuple[str, ...] = Field(min_length=1)


class CustomerReplyReview(RuleSpec):
    kind: Literal["customer_reply_review"]


class ReleaseApprovalReview(RuleSpec):
    kind: Literal["release_approval"]
    roles: tuple[TeamRole, ...] = Field(min_length=1)


PolicyRule = Annotated[
    RequiredReadsRule
    | DisputedPaymentRule
    | DuplicateRefundRule
    | RefundLimitRule
    | CustomerOrderRule
    | DeliveredOrderRule
    | RefundRetryRule,
    Field(discriminator="kind"),
]
ReviewRule = Annotated[
    CustomerReplyReview | ReleaseApprovalReview,
    Field(discriminator="kind"),
]


class WorkflowSpec(LibraryRecord):
    title: str = Field(min_length=1)
    tools: tuple[WorkflowTool, ...] = Field(min_length=1)
    stages: tuple[WorkflowStage, ...] = Field(min_length=1)
    outcomes: tuple[Outcome, ...] = Field(min_length=1)
    rules: tuple[PolicyRule, ...]
    reviews: tuple[ReviewRule, ...]

    @property
    def tool_names(self) -> frozenset[str]:
        return frozenset(tool.name for tool in self.tools)

    @model_validator(mode="after")
    def references_declared_tools(self) -> Self:
        _require_unique("tool name", (tool.name for tool in self.tools))
        _require_unique("rule id", (rule.id for rule in (*self.rules, *self.reviews)))
        _require_unique("outcome", self.outcomes)
        if Outcome.NO_RESOLUTION in self.outcomes:
            raise ValueError("no_resolution cannot be a valid workflow outcome")
        for stage in self.stages:
            _require_subset(f"Stage {stage.id}", stage.tools, self.tool_names)
        read_tools = {tool.name for tool in self.tools if tool.access is ToolAccess.READ}
        for rule in self.rules:
            if isinstance(rule, RequiredReadsRule | RefundRetryRule):
                _require_subset(f"Rule {rule.id}", rule.tools, read_tools)
        return self


class Scenario(LibraryRecord):
    workflow_id: Identifier
    title: str = Field(min_length=1)
    pattern: ScenarioPattern
    author: TeamRole
    conversation_id: str = Field(min_length=1)
    initial_state: RefundState
    faults: tuple[ToolFault, ...] = ()
    expected_outcomes: tuple[Outcome, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def conversation_is_seeded(self) -> Self:
        if self.conversation_id not in self.initial_state.conversations:
            raise ValueError(f"Conversation {self.conversation_id} is not in the initial state")
        _require_unique("expected outcome", self.expected_outcomes)
        return self


class ScriptedCall(LibraryModel):
    tool: str = Field(min_length=1)
    arguments: dict[str, JsonValue]


class AgentScript(LibraryRecord):
    scenario_id: Identifier
    agent_id: Identifier
    agent_version: str = Field(min_length=1)
    rerun_of: Identifier | None = None
    calls: tuple[ScriptedCall, ...] = Field(min_length=1)


def _require_unique(label: str, values: Iterable[str]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"Duplicate {label}: {value}")
        seen.add(value)


def _require_subset(owner: str, values: Iterable[str], allowed: Collection[str]) -> None:
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise ValueError(f"{owner} references undeclared tools: {', '.join(unknown)}")
