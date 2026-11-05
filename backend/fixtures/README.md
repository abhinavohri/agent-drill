# Fixtures

## Refund scenario library

`refunds/` is the scenario and policy library for the refund workflow.

- `workflows/` contains workflow specifications with their tools, stages, outcomes, rules, and review checks.
- `scenarios/` contains the valid, disputed, duplicate, and timeout scenarios.
- `agent_scripts/` contains scripted target-agent runs. Each scenario has an unsafe run and a safe rerun.
- `reviews/` contains reviewer decisions for the safe reruns.
- `runs/`, `results/`, and `reports/` are generated. Run `uv run python -m app.jobs.build_refund_fixtures` from `backend/` to regenerate them.

## Temporary handoff fixtures

These files let each workstream start before the shared contracts are complete.

- `stubs/run-request.json` stands in for the Switch run request from Ojas.
- `stubs/refund-scenario.json` stands in for the scenario from Maqsud. `refunds/scenarios/disputed-payment-750.json` replaces it after team approval.
- `stubs/target-agent-calls.json` stands in for target-agent MCP calls.
- `stubs/target-agent-responses.json` stands in for target-agent messages.
- `stubs/run-events.json` and `stubs/final-state.json` are the evaluator handoff from Abhinav.
- `production_traces/disputed-payment.json` is the redacted trace-ingestion example for Maqsud.

Replace each stub with its approved shared contract. Do not add production secrets or customer data.
