# External providers

## Tool provider

The tool provider owns tool discovery and execution for the Drill MCP server. Local runs use the refund provider and stateful refund world. The explicit mock remains available for focused proxy tests.

A real provider must return validated tool definitions and typed tool results. It must own transport errors and connection cleanup.

Do not connect the simulation runtime to a production tool endpoint. Use a synthetic world, an official sandbox, or a dedicated test tenant.

## Sandbox provider

The sandbox provider prepares and cleans an isolated test environment for a run. The first implementation records leases in memory.

A real provider can use an official service sandbox, a temporary database, or a dedicated test tenant. It must not expose production credentials or endpoints.

