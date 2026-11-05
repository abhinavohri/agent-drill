"""HTTP boundary for simulation run inspection."""

from fastapi import APIRouter, HTTPException, status

from app.simulations.internal.models import SimulationRun
from app.simulations.internal.schemas import StartRunRequest
from app.simulations.internal.service import (
    RunNotActiveError,
    RunNotFoundError,
    SimulationService,
)


def build_router(service: SimulationService) -> APIRouter:
    router = APIRouter(prefix="/runs", tags=["simulation-runs"])

    @router.post("", response_model=SimulationRun, status_code=status.HTTP_201_CREATED)
    async def start_run(request: StartRunRequest) -> SimulationRun:
        return await service.start_run(request.scenario_id, request.max_actions)

    @router.get("/{run_id}", response_model=SimulationRun)
    async def get_run(run_id: str) -> SimulationRun:
        try:
            return service.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post("/{run_id}/stop", response_model=SimulationRun)
    async def stop_run(run_id: str) -> SimulationRun:
        try:
            return await service.stop_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RunNotActiveError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return router

