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

