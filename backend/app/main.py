"""Assemble the Agent Drill HTTP application."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from app.simulations.facade import MockSandbox, SimulationService, build_router


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Drill", version="0.1.0")
    simulations = SimulationService(MockSandbox())
    app.include_router(build_router(simulations))

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    return app


app = create_app()

