# Agent Drill

Agent Drill runs real agent tool code against safe test environments. The backend includes simulation runs, a Drill MCP proxy, a stateful refund world, a refund scenario library, and a deterministic evaluator that writes Markdown reports.

See [backend/README.md](backend/README.md) for setup and commands.

`targets/` holds adapters that run third-party agents as drill targets.
[targets/holmesgpt](targets/holmesgpt/README.md) drills HolmesGPT on the refund scenarios and
keeps its ATIF traces.

Use [docs/switch-telegram.md](docs/switch-telegram.md) to connect the project agent to Telegram through Switch.

## Release review in Switch

Agent Drill joins a [Switch](https://docs.switchagents.ai/) room as a teammate. The team asks it to
drill a support agent, reads the evidence in the room, and approves or blocks the release there.

- **Agents**: Agent Drill is a Claude Code or Codex agent that Switch Console runs in this
  repository. The support agent under test, HolmesGPT, runs inside each drill and can use only the
  simulated refund tools.
- **Room**: [switch/release-review.template.yaml](switch/release-review.template.yaml) creates
  Agent Drill and a review room on Mattermost, which comes with Switch. It can add Agent Drill to an
  existing room, such as a Telegram group, instead. A support reviewer and a finance reviewer
  decide in the room.
- **Run**: follow [switch/README.md](switch/README.md).

## Preview the landing page

```sh
cd website
python3 -m http.server 4173
```

Open <http://localhost:4173>.

