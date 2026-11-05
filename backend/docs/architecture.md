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

`app/main.py` assembles the HTTP application. `app/jobs/drill_mcp.py` is the stable stdio MCP entry point.

