"""Opt-in traffic and disconnect acceptance against an isolated real Mihomo."""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from fastapi import FastAPI
import httpx
import pytest

from api.clash import router
from core.auth import require_auth
from core.clash import ClashManager, ClashProfileInput
from core.service_state import ServiceState

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    os.getenv("R_LINK_RUN_CLASH_INTEGRATION") != "1", reason="Opt-in real Mihomo integration")]


async def test_real_traffic_counters_and_selective_disconnect(tmp_path):
    binary = os.getenv("R_LINK_MIHOMO_BINARY")
    if not binary or not Path(binary).is_file():
        pytest.fail("Set R_LINK_MIHOMO_BINARY to an installed Mihomo executable")
    manager = ClashManager(ServiceState(tmp_path))
    app = FastAPI()
    app.include_router(router)
    app.state.services = SimpleNamespace(ready=True, clash=manager)
    app.dependency_overrides[require_auth] = lambda: {"id": "integration-operator"}
    upstream_writers = set()

    async def echo(reader, writer):
        upstream_writers.add(writer)
        try:
            while chunk := await reader.read(65536):
                writer.write(chunk)
                await writer.drain()
        finally:
            upstream_writers.discard(writer)
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(echo, "127.0.0.1", 0)
    upstream_port = server.sockets[0].getsockname()[1]
    clients = []
    try:
        profile = await manager.save_profile(ClashProfileInput(
            name="traffic acceptance", content="mode: direct\nlog-level: warning\nproxies: []\nrules: []\n"))
        await manager.start_managed(profile["id"])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://rlink.test") as api:
            for _ in range(40):
                if (await manager.status())["connected"]:
                    break
                await asyncio.sleep(.1)
            assert (await manager.status())["connected"]
            configs = await manager.configs()
            initial = (await api.get("/api/clash/traffic")).json()
            for _ in range(2):
                reader, writer = await asyncio.open_connection("127.0.0.1", configs["mixed_port"])
                clients.append((reader, writer))
                writer.write(f"CONNECT 127.0.0.1:{upstream_port} HTTP/1.1\r\nHost: 127.0.0.1:{upstream_port}\r\n\r\n".encode())
                await writer.drain()
                response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
                assert b"200" in response.split(b"\r\n")[0]
            payload = b"rlink-traffic-proof" * 4096
            for reader, writer in clients:
                writer.write(payload)
                await writer.drain()
                assert await asyncio.wait_for(reader.readexactly(len(payload)), 5) == payload
            for _ in range(40):
                response = await api.get("/api/clash/traffic")
                assert response.status_code == 200, response.text
                snapshot = response.json()
                if snapshot["downloadTotal"] - initial["downloadTotal"] >= 2 * len(payload):
                    break
                await asyncio.sleep(.1)
            assert snapshot["source_id"] == initial["source_id"]
            assert snapshot["sampled_at"] > initial["sampled_at"]
            assert snapshot["downloadTotal"] - initial["downloadTotal"] >= 2 * len(payload)
            assert snapshot["uploadTotal"] - initial["uploadTotal"] >= 2 * len(payload)
            assert snapshot["total_connections"] == 2 and snapshot["truncated"] is False
            assert len(snapshot["connections"]) == 2
            assert all(item["download"] >= len(payload) and item["upload"] >= len(payload)
                       for item in snapshot["connections"])
            first = snapshot["connections"][0]["id"]
            survivor = snapshot["connections"][1]["id"]
            first_url = "/api/clash/connections/" + quote(first, safe="")
            assert (await api.delete(first_url, params={"source_id": "stale-source"})).status_code == 409
            assert (await api.get("/api/clash/traffic")).json()["total_connections"] == 2
            assert (await api.delete(first_url, params={"source_id": snapshot["source_id"]})).status_code == 204
            after = (await api.get("/api/clash/traffic")).json()
            assert [item["id"] for item in after["connections"]] == [survivor]
            assert (await api.delete("/api/clash/connections", params={"source_id": after["source_id"]})).status_code == 204
            assert (await api.get("/api/clash/traffic")).json()["connections"] == []
    finally:
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()
        await manager.close()
        server.close()
        await server.wait_closed()
        for writer in list(upstream_writers):
            writer.close()
