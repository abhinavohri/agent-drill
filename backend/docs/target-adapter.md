# Target command adapter contract

Status: v1

A target adapter starts one agent run and converts the agent's native output to ATIF v1.7. Agent
Drill owns command execution, environment isolation, time limits, trace validation, and run status.

## Configuration

```json
{
  "kind": "command",
  "command": [
    "python",
    "run_target.py",
    "--task",
    "{task}",
    "--mcp-url",
    "{mcp_url}",
    "--trace",
    "{trace_path}"
  ],
  "working_directory": "/path/to/target",
  "inherit_environment": ["PATH", "MODEL_API_KEY"],
  "environment": {},
  "timeout_seconds": 600,
  "trace_path": "runs/{scenario_id}/trajectory.json"
}
```

Do not put credentials in the configuration. Name each required credential in
`inherit_environment`.

## Command values

| Placeholder | Value |
| --- | --- |
| `{scenario_id}` | Stable identifier for the selected scenario. |
| `{task}` | Complete task text for the target agent. |
| `{mcp_url}` | Streamable HTTP MCP URL for the safe tool environment. |
| `{trace_path}` | Absolute path for the required ATIF artifact. |
| `{output_dir}` | Directory that contains the ATIF artifact. |
| `{policy_file}` | Absolute path to the policy text when the run supplies one. |

The `trace_path` configuration can use `{scenario_id}`. Agent Drill rejects other placeholders in
that field. A run fails before command execution when the command needs a value that is absent.

## Adapter requirements

1. Use the supplied task without changing its meaning.
2. Connect simulated tools to the supplied MCP URL.
3. Disable production tools and host tools that can bypass the simulated environment.
4. Write one ATIF v1.7 trajectory to the supplied trace path.
5. Set the ATIF agent name and version. Set the model name when it is known.
6. Include tool calls, tool results, the final response, and available usage metrics in the trace.
7. Exit with code 0 only after the complete trace is written.
8. Write diagnostic details to standard error when the run fails.

Agent Drill captures standard output and standard error. It rejects a successful command when the
trace is missing or invalid.
