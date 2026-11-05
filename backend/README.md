# Agent Drill backend

## Setup

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Run the HTTP backend

```sh
.venv/bin/uvicorn app.main:app --reload
```

## Run the fixture-backed Drill MCP server

```sh
.venv/bin/python -m app.jobs.drill_mcp
```

The MCP process loads the disputed-payment fixture. It exposes the eight refund tools through a stateful local world. It does not use a production endpoint or credential.

Temporary cross-team inputs and outputs are in `fixtures/`. Replace them with the approved shared contracts when they are available.

## Check the backend

```sh
.venv/bin/ruff check app tests
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

