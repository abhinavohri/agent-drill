# External providers

## Upstream MCP provider

The upstream MCP provider owns connection and calls to the target agent's existing MCP server. The first implementation is an explicit mock.

A real provider must return validated tool definitions and typed tool results. It must own transport errors and connection cleanup.

## Sandbox provider

The sandbox provider prepares and cleans an isolated test environment for a run. The first implementation records leases in memory.

A real provider can use an official service sandbox, a temporary database, or a dedicated test tenant. It must not expose production credentials or endpoints.

