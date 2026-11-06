"""Validate ATIF documents at the file and text boundaries."""

import json
from pathlib import Path

from atif import Trajectory
from pydantic import ValidationError

SUPPORTED_SCHEMA_VERSION = "ATIF-v1.7"


class TraceInputError(ValueError):
    pass


def parse_atif(content: str | bytes) -> Trajectory:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TraceInputError(f"Invalid ATIF JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TraceInputError("Invalid ATIF trajectory: the root value must be an object")
    schema_version = data.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise TraceInputError(
            f"Unsupported ATIF schema version {schema_version!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION!r}"
        )
    try:
        trajectory = Trajectory.model_validate(data)
    except ValidationError as exc:
        raise TraceInputError(f"Invalid ATIF trajectory: {exc}") from exc
    return trajectory


def load_atif(path: Path) -> Trajectory:
    try:
        return parse_atif(path.read_bytes())
    except OSError as exc:
        raise TraceInputError(f"Cannot read {path}: {exc}") from exc
