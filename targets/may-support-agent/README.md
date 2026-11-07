# May support agent target

This connector runs the May support triage agent through the stable command adapter. The target has
local retrieval and no external tools, so it does not use an MCP server.

The May repository must be a sibling of `agent-drill`:

```text
workspace/
├── agent-drill/
└── hackerrank-orchestrate-may26/
```

Install the ATIF contract into the May agent environment:

```sh
cd targets/may-support-agent
uv pip install --python ../../../hackerrank-orchestrate-may26/.venv/bin/python \
  -r requirements.txt
```

Run one ticket from `backend/`:

```sh
uv run python -m app.jobs.run_drill \
  ../targets/may-support-agent/drill.json \
  password-reset \
  --task '{"issue":"How do I reset my password?","subject":"Password reset","company":"Claude"}'
```

The connector also accepts plain task text. It uses `company="None"` and an empty subject for plain
text.
