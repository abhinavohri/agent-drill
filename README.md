# Agent Drill

Agent Drill runs real agent tool code against safe test environments. The backend includes simulation runs, a Drill MCP proxy, a stateful refund world, a refund scenario library, and a deterministic evaluator that writes Markdown reports.

See [backend/README.md](backend/README.md) for setup and commands.

`targets/` holds adapters that run third-party agents as drill targets.
[targets/holmesgpt](targets/holmesgpt/README.md) drills HolmesGPT on the refund scenarios and
keeps its ATIF traces.

Use [docs/switch-telegram.md](docs/switch-telegram.md) to connect the project agent to Telegram through Switch.

## Preview the landing page

```sh
cd website
python3 -m http.server 4173
```

Open <http://localhost:4173>.

