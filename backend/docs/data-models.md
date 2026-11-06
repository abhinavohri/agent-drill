# Backend data models

Use Pydantic models for stable run, event, tool, and provider contracts.

Use dataclasses for private mutable run records. Return immutable Pydantic snapshots from public operations.

JSON Schema, generic MCP values, and serialized final state can use JSON dictionaries at their wire boundaries. Known event payloads, state changes, refund arguments, and refund results use typed models.

The refund fixture loader validates temporary scenario JSON as `RefundScenario`. The refund world keeps one deep state copy for each run and exports the final state as JSON.

`WorkflowSpec`, `Scenario`, and `AgentScript` are library contracts in the `workflows` domain. Policy rules and review rules are separate discriminated unions, so a workflow file cannot move a hard rule into the review tier.

`RecordedRun` wraps a `SimulationRun` snapshot with the pinned agent, agent version, and workflow. `RunResult` holds the verdict, the outcome, the six checks with rule-level evidence, the tool actions, and the pending approvals. Evidence refers to run event sequence numbers and state paths. `ReviewInput` holds reviewer decisions and language-model judge assessments.

The evaluator converts recorded tool arguments to the refund argument models before any rule uses them. A call with an unknown tool or invalid arguments becomes a rejected action instead of a typed attempt.

The files in `fixtures/stubs/` are temporary handoff records. Shared contracts replace them after team approval.

