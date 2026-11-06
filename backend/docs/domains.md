# Domain packages

## Drills

`app/drills/` owns target-runner contracts, command execution, time limits, and target run results.
It validates the ATIF artifact through the `traces` facade. It contains no target-specific logic.

Its facade exports the runner contract, command runner, configuration, and run result.

## Drill MCP

`app/drill_mcp/` owns generic tool discovery, tool-call validation, proxying, timeout handling, and MCP protocol translation.

Its facade exports the proxy service, provider contract, mock provider, and stdio server operation.

## Simulations

`app/simulations/` owns run lifecycle, action limits, ordered events, and sandbox preparation and cleanup.

Its facade exports the simulation service, stable run models, sandbox contract, mock sandbox, and HTTP router assembly.

## Refunds

`app/refunds/` owns the eight refund tool contracts, validated scenario state, fault injection, and stateful tool behavior.

Its facade exports the refund tool provider, refund world, scenario state and tool-argument models, the tool-to-argument map, and the temporary scenario fixture loader. Replace the loader with the `workflows` library when the team approves the shared `Scenario` contract.

## Workflows

`app/workflows/` owns workflow specifications, the scenario and policy library, and the scripted target-agent runs in `fixtures/refunds/`. Its parser validates each library file and the references between files.

Its facade exports `WorkflowSpec`, `Scenario`, `AgentScript`, the policy and review rule types, and the library loader.

## Evaluations

`app/evaluations/` owns deterministic run evaluation, pass, fail, and review verdicts, run comparison, and Markdown reports. It reads recorded runs. It does not call tools, network services, or language models.

Its facade exports `evaluate_run`, `compare_results`, the report renderers, and the `RecordedRun`, `ReviewInput`, `RunResult`, and `RunComparison` contracts.

Hard checks (input schema, tool permissions, action order and invariants, and final state) use only the recorded run. Reviewer decisions and language-model judge assessments resolve only the semantic-output and human-approval checks, so they cannot override a hard failure.

## Traces

`app/traces/` owns ATIF trace validation and file ingestion. It uses the published ATIF
Pydantic models and does not define a competing trace format.

Its facade exports the ATIF `Trajectory` contract and the text and file ingestion operations.

## Process entry points

`app/jobs/` is not a domain package. It contains stable process entry points that use domain facades.

