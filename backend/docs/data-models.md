# Backend data models

Use Pydantic models for stable run, event, tool, and provider contracts.

Use dataclasses for private mutable run records. Return immutable Pydantic snapshots from public operations.

JSON Schema, generic MCP values, and serialized final state can use JSON dictionaries at their wire boundaries. Known event payloads, state changes, refund arguments, and refund results use typed models.

The refund fixture loader validates temporary scenario JSON as `RefundScenario`. The refund world keeps one deep state copy for each run and exports the final state as JSON.

The files in `fixtures/stubs/` are temporary handoff records. Shared contracts replace them after team approval.

