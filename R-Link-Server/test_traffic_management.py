"""Bounded, authenticated Clash traffic snapshots."""

import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from api.clash import router
from core.auth import require_auth
from core.clash import MAX_CONNECTIONS, ClashManager, ClashSettingsInput
from core.service_state import ServiceState


def make_app(manager: ClashManager) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.services = SimpleNamespace(ready=True, clash=manager)
    return app


@pytest.mark.asyncio
async def test_traffic_endpoint_requires_auth(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    app = make_app(manager)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/clash/traffic", headers={"Origin": "https://evil.invalid"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_traffic_snapshot_has_real_counters_and_metadata_allowlist(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    manager._json_request = AsyncMock(return_value={
        "downloadTotal": 123456,
        "uploadTotal": 789,
        "connections": [{
            "id": "connection-1",
            "start": "2026-10-11T01:02:03Z",
            "upload": 17,
            "download": 29,
            "chains": ["DIRECT"],
            "rule": "MATCH",
            "metadata": {
                "process": "Safari",
                "processPath": "/Users/private/secret-app",
                "inbound": "Bearer private-inbound-token",
                "sourceIP": "192.0.2.10",
            },
        }],
    })

    snapshot = await manager.traffic()

    assert isinstance(snapshot["sampled_at"], float)
    assert snapshot["downloadTotal"] == 123456
    assert snapshot["uploadTotal"] == 789
    assert snapshot["connections"][0]["metadata"] == {
        "sourceIP": "192.0.2.10",
        "process": "Safari",
    }
    assert "processPath" not in snapshot["connections"][0]["metadata"]
    assert "inbound" not in snapshot["connections"][0]["metadata"]
    assert snapshot["total_connections"] == 1
    assert snapshot["truncated"] is False
    assert snapshot["source_id"].startswith("clash-src-v1-")
    assert "private-inbound-token" not in str(snapshot)


@pytest.mark.asyncio
async def test_traffic_source_id_is_stable_and_resets_for_target_changes(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    manager._json_request = AsyncMock(return_value={"downloadTotal": 0, "uploadTotal": 0, "connections": []})

    first = await manager.traffic()
    second = await manager.traffic()
    assert first["source_id"] == second["source_id"]

    await manager.save_settings(ClashSettingsInput(
        controller_url="https://controller.example:443",
        secret="private-controller-secret",
    ))
    changed = await manager.traffic()
    assert changed["source_id"] != first["source_id"]
    assert "private-controller-secret" not in changed["source_id"]
    assert "controller.example" not in changed["source_id"]

    manager.process.status = lambda: {"state": "running", "pid": 1234}
    manager._managed_target = {"controller_url": "http://127.0.0.1:19090", "secret": "managed-secret-a"}
    managed_first = await manager.traffic()
    manager._managed_target = {"controller_url": "http://127.0.0.1:19091", "secret": "managed-secret-b"}
    managed_changed = await manager.traffic()
    assert managed_changed["source_id"] != managed_first["source_id"]
    assert "managed-secret-a" not in managed_first["source_id"]
    assert "managed-secret-b" not in managed_changed["source_id"]


@pytest.mark.asyncio
async def test_traffic_rejects_controller_switch_during_snapshot(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")

    async def switch_target(*_args, **_kwargs):
        manager.state.save("settings", {"controller_url": "http://127.0.0.1:9091"}, "clash")
        manager._traffic_target_revision += 1
        return {"downloadTotal": 1, "uploadTotal": 2, "connections": []}

    manager._json_request = switch_target

    with pytest.raises(HTTPException, match="目标已变化") as error:
        await manager.traffic()
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_close_rejects_wrong_source_without_delete(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    manager._response = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await manager.close_connections("connection-1", source_id="clash-src-v1-wrong")

    assert error.value.status_code == 409
    manager._response.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_uses_valid_source_target_and_rejects_context_switch(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    manager._json_request = AsyncMock(return_value={"downloadTotal": 1, "uploadTotal": 2, "connections": []})
    source_id = (await manager.traffic())["source_id"]
    manager._response = AsyncMock()

    await manager.close_connections("connection-1", source_id=source_id)
    manager._response.assert_awaited_once_with(
        "DELETE",
        "/connections/connection-1",
        target=("http://127.0.0.1:9090", None),
    )

    async def switch_on_delete(*_args, **_kwargs):
        manager.state.save("settings", {"controller_url": "http://127.0.0.1:9091"}, "clash")
        manager._traffic_target_revision += 1

    manager._response = switch_on_delete
    with pytest.raises(HTTPException, match="流量来源已变化") as error:
        await manager.close_connections("connection-1", source_id=source_id)
    assert error.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    None,
    [],
    {},
    {"connections": []},
    {"downloadTotal": 1, "connections": []},
    {"uploadTotal": 2, "connections": []},
    {"downloadTotal": 1, "uploadTotal": 2},
    {"downloadTotal": float("nan"), "uploadTotal": 2, "connections": []},
    {"downloadTotal": 1, "uploadTotal": float("inf"), "connections": []},
    {"downloadTotal": 1, "uploadTotal": 2, "connections": {}},
])
async def test_traffic_rejects_invalid_snapshot_shapes_and_nonfinite_numbers(tmp_path, payload):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    manager._json_request = AsyncMock(return_value=payload)

    with pytest.raises(HTTPException) as error:
        await manager.traffic()
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_traffic_accepts_null_connections_as_empty_snapshot(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    manager._json_request = AsyncMock(return_value={"downloadTotal": 1, "uploadTotal": 2, "connections": None})

    snapshot = await manager.traffic()

    assert math.isfinite(snapshot["sampled_at"])
    assert snapshot["connections"] == []
    assert snapshot["total_connections"] == 0
    assert snapshot["truncated"] is False


@pytest.mark.asyncio
async def test_traffic_marks_connection_snapshot_truncation(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    raw_connections = [{"id": str(index), "metadata": {"process": "App"}} for index in range(MAX_CONNECTIONS + 2)]
    manager._json_request = AsyncMock(return_value={
        "downloadTotal": 1,
        "uploadTotal": 2,
        "connections": raw_connections,
    })

    snapshot = await manager.traffic()

    assert len(snapshot["connections"]) == MAX_CONNECTIONS
    assert snapshot["total_connections"] == MAX_CONNECTIONS + 2
    assert snapshot["truncated"] is True


@pytest.mark.asyncio
async def test_authenticated_traffic_route_returns_snapshot(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save("settings", {"controller_url": "http://127.0.0.1:9090"}, "clash")
    manager._json_request = AsyncMock(return_value={"downloadTotal": 10, "uploadTotal": 20, "connections": []})
    app = make_app(manager)
    app.dependency_overrides[require_auth] = lambda: {"id": "traffic-test"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/clash/traffic")

    assert response.status_code == 200
    assert response.json()["downloadTotal"] == 10
    assert response.json()["uploadTotal"] == 20
    assert response.json()["total_connections"] == 0
