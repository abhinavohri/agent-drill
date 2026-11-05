"""Sandbox provider contract and the first mock implementation."""

from typing import Protocol


class Sandbox(Protocol):
    async def prepare(self, run_id: str, scenario_id: str) -> str: ...

    async def cleanup(self, sandbox_id: str) -> None: ...


class MockSandbox:
    """Track isolated sandbox leases without calling an external service."""

    def __init__(self) -> None:
        self.active_ids: set[str] = set()

    async def prepare(self, run_id: str, scenario_id: str) -> str:
        sandbox_id = f"mock-{scenario_id}-{run_id}"
        self.active_ids.add(sandbox_id)
        return sandbox_id

    async def cleanup(self, sandbox_id: str) -> None:
        self.active_ids.discard(sandbox_id)

