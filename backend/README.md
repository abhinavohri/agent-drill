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

## Check the backend

```sh
uv run ruff check app tests
uv run python -m unittest discover -s tests -p 'test_*.py'
```

