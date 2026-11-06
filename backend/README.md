# Agent Drill backend

## Setup

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync
```

`uv sync` uses the Python version in `.python-version`, creates `.venv`, and installs the locked dependencies from `uv.lock`, including the development tools.

Add a runtime dependency with `uv add <package>` and a development tool with `uv add --dev <package>`. Commit `pyproject.toml` and `uv.lock` together.

## Run the HTTP backend

```sh
uv run uvicorn app.main:app --reload
```

## Run the fixture-backed Drill MCP server

```sh
uv run python -m app.jobs.drill_mcp
```

The MCP process loads the disputed-payment fixture. It exposes the eight refund tools through a stateful local world. It does not use a production endpoint or credential.

Temporary cross-team inputs and outputs are in `fixtures/`. Replace them with the approved shared contracts when they are available.

## Ingest an ATIF trace

```sh
uv run python -m app.jobs.ingest_trace \
  fixtures/production_traces/shopping-agent.atif.json
```

The command validates one ATIF v1.7 trajectory and writes normalized JSON to standard output. Use
`--output PATH` to write the normalized trajectory to a file.

## Run a target command

Create a JSON configuration:

```json
{
  "kind": "command",
  "command": ["python", "-m", "target_agent", "--scenario", "{scenario_id}"],
  "working_directory": "/path/to/target",
  "inherit_environment": ["PATH"],
  "environment": {},
  "timeout_seconds": 600,
  "trace_path": "runs/{scenario_id}/trajectory.json"
}
```

Run one scenario:

```sh
uv run python -m app.jobs.run_drill drill.json scenario-1
```

The target command must write an ATIF v1.7 trajectory to `trace_path`. Agent Drill returns a typed
result with the execution status, duration, output, and trace metadata. Do not put secrets in the
configuration. The target command inherits only the environment variables named in
`inherit_environment`.

## Drill a target agent on a refund scenario

```sh
uv run python -m app.jobs.run_refund_drill ../targets/holmesgpt/drill.json valid-refund \
  --output ../targets/holmesgpt/runs/no-policy/valid-refund/r1
```

The job loads the scenario from `fixtures/refunds/` and serves its eight refund tools over MCP
streamable HTTP on a local port. It then runs the target command from the configuration. All MCP
sessions share one refund world and one recorded run, so a target can open a new session for each
tool call.

Besides `{scenario_id}`, the command and `trace_path` can use these placeholders:

- `{mcp_url}`: the Drill MCP URL
- `{conversation_id}`: the scenario's support conversation
- `{output_dir}`: the output directory
- `{policy_file}`: the workflow rules in plain language, written to `policy.md`

When the target exits, the job writes `drill-run.json`, `recorded-run.json`, `result.json`, and
`report.md` to the output directory. It takes the agent name and version from the target's ATIF
trace. If the target fails, the job still records and grades the run, and it exits with code 1.

## Evaluate a saved run

```sh
uv run python -m app.jobs.evaluate_run fixtures/refunds/runs/disputed-payment-750.unsafe.json
uv run python -m app.jobs.evaluate_run fixtures/refunds/runs/disputed-payment-750.safe.json \
  --review fixtures/refunds/reviews/disputed-payment-750.safe.json \
  --compare-with fixtures/refunds/runs/disputed-payment-750.unsafe.json
```

The first command reports FAIL with the unsafe refund call, the failed rules, their evidence, and the final synthetic state. The second command reports PASS after the finance approval and compares the corrected rerun with the original run. Add `--result-json PATH` to save the `RunResult` and `--report PATH` to write the Markdown report to a file.

## Regenerate the refund fixtures

```sh
uv run python -m app.jobs.build_refund_fixtures
```

The job plays each script in `fixtures/refunds/agent_scripts/` against the refund world through the Drill proxy. It then writes the saved runs, results, and reports in `fixtures/refunds/`.

## Check the backend

```sh
uv run ruff check app tests
uv run python -m unittest discover -s tests -p 'test_*.py'
```

