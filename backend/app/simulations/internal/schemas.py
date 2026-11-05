"""HTTP request models for simulation operations."""

from pydantic import BaseModel, Field


class StartRunRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    max_actions: int = Field(default=20, ge=1, le=1000)

