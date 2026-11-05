"""Assemble the Agent Drill HTTP application."""

from fastapi import FastAPI

from app.simulations.facade import MockSandbox, SimulationService, build_router


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Drill", version="0.1.0")
    simulations = SimulationService(MockSandbox())
    app.include_router(build_router(simulations))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

