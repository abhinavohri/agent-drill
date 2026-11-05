import unittest

from httpx import ASGITransport, AsyncClient

from app.main import create_app


class RouteValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=create_app())
        self.client = AsyncClient(transport=transport, base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_rejects_null_scenario_at_http_boundary(self) -> None:
        response = await self.client.post("/runs", json={"scenario_id": None})

        self.assertEqual(response.status_code, 422)

    async def test_health_returns_typed_response(self) -> None:
        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def test_start_run_returns_typed_event_payload(self) -> None:
        response = await self.client.post("/runs", json={"scenario_id": "scenario_1"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "running")
        self.assertEqual(response.json()["events"][0]["payload"], {"scenarioId": "scenario_1"})
