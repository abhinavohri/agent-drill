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

## Run the mock MCP proxy

```sh
.venv/bin/python -m app.jobs.drill_mcp
```

The MCP process uses a mock upstream MCP provider and a mock sandbox. Replace these providers through the public domain contracts when a target agent is available.

## Check the backend

```sh
.venv/bin/ruff check app tests
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

