# Backend architecture

The backend is a domain-oriented modular monolith.

Each domain has one public facade and private implementation files:

```text
app/<domain>/
├── facade.py
└── internal/
    ├── providers/
    └── <implementation>.py
```

Use only the files that the domain needs.

## Dependency direction

```text
main and jobs -> domain facade -> domain internal code
                            \-> other domain facade
```

The `drill_mcp` domain can import the `simulations` facade. It must not import simulation internal files.

The `refunds` domain implements the generic Drill tool-provider contract. The process entry point connects that provider to the Drill proxy. The generic Drill domain does not import the refund domain.

The `workflows` domain imports the `refunds` facade for scenario state and the refund tool catalog.

The `evaluations` domain imports the `workflows`, `simulations`, and `refunds` facades. No domain imports `evaluations`. Only process entry points use it.

The `workflows` domain defines both saved workflow scenarios and declarative ad hoc scenarios. A
refund scenario seed contains starting conditions only. The `refunds` domain creates consistent
synthetic state from that seed.

The `traces` domain validates external ATIF documents. It has no dependency on a target-agent
domain. Process entry points and future evaluators use its facade.

The `drills` domain imports the `traces` facade. It runs a target through a configured runner and
returns target-independent run metadata. A future MCP runner implements the same public contract.

`app/main.py` assembles the HTTP application. `app/jobs/drill_mcp.py` is the stable stdio MCP entry point. `app/jobs/ingest_trace.py` validates and normalizes one ATIF trajectory. `app/jobs/run_drill.py` runs one target command and validates its ATIF artifact. `app/jobs/run_ad_hoc_drill.py` runs real target code against a declarative direct or refund environment. `app/jobs/run_refund_drill.py` connects one library scenario's refund world to the Drill proxy, serves it over MCP streamable HTTP, runs a target command against it, and grades the recorded run. `app/jobs/evaluate_run.py` evaluates a saved run and writes its report. `app/jobs/build_refund_fixtures.py` plays the scripted agent runs against the refund world through the Drill proxy and regenerates the saved runs, results, and reports.

