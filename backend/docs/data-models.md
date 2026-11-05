# Backend data models

Use Pydantic models for stable run, event, tool, and provider contracts.

Use dataclasses for private mutable run records. Return immutable Pydantic snapshots from public operations.

JSON Schema and event payloads have dynamic key sets. They can use JSON dictionaries at their wire boundaries.

