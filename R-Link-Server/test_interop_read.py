"""Product read handlers over ASGI: native authority, replay, epochs and soft cancel."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from api import devices as native_api
from api import interop as bridge_api
from core import devices, identity
from interop_bridge import Client, ContractError, validate
from interop_bridge._vendor.r_sdk_interop import check_response

PREFIX = "R_LINK_INTEROP"
APP = "r-link"
OPERATION = "r-link.devices.list"
RESOURCE = "devices"
TOKEN = "disposable-interop-test-token-000000000000"


def frame(kind: str, body: dict, generation: int = 1) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "kind": kind,
        "requestId": str(uuid4()),
        "correlationId": str(uuid4()),
        "generation": generation,
        "body": body,
    }


def read_request(timeout: int = 1000, generation: int = 1) -> dict:
    return frame(
        "agent.request",
        {
            "operation": OPERATION,
            "target": {
                "appId": APP,
                "appInstanceId": "native-instance",
                "deviceId": "native-device",
                "resourceId": RESOURCE,
            },
            "mode": "read_only",
            "expectedResourceRevision": None,
            "capabilityRef": None,
            "approvalRef": None,
            "timeoutMs": timeout,
            "arguments": {"limit": 10},
        },
        generation=generation,
    )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    for key, value in {
        "READ_ENABLED": "1",
        "INSTANCE_ID": "native-instance",
        "DEVICE_ID": "native-device",
        "GENERATION": "1",
        "STATE_DIR": str(tmp_path / "journal"),
    }.items():
        monkeypatch.setenv(PREFIX + "_" + key, value)
    for key, value in {
        "R_LINK_AUTH_MODE": "oidc",
        "R_LINK_OIDC_ISSUER": "https://identity.example.test",
        "R_LINK_OIDC_CLIENT_ID": "test-link",
        "R_LINK_OIDC_CLIENT_SECRET": "disposable-client-secret",
        "R_LINK_PUBLIC_URL": "https://app.example.test",
        "R_LINK_AUTH_DB": str(tmp_path / "auth.sqlite"),
        "R_LINK_DEVICES_DB": str(tmp_path / "devices.sqlite"),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("R_LINK_API_TOKEN", raising=False)
    monkeypatch.delenv("R_LINK_BOOTSTRAP_ADMIN_SUBJECT", raising=False)
    user = identity.upsert_identity(
        {"iss": "https://identity.example.test", "sub": "native-test-viewer"}
    )
    with identity.database() as db:
        db.execute("UPDATE users SET role='viewer' WHERE id=?", (user["id"],))
    session = identity.create_session(user, "desktop")
    record = devices.save_device(
        devices.DeviceInput(name="Actual NAS Metadata", host="nas.example.test")
    )
    app = FastAPI()
    app.include_router(bridge_api.router)
    return SimpleNamespace(
        app=app,
        headers={
            "Authorization": "Bearer " + session["token"],
            "X-R-Link-Session-Context": session["id"],
        },
        device_id=record["id"],
        monkeypatch=monkeypatch,
        revoke=lambda: identity.revoke_session(session["id"]),
    )


async def send(
    world: SimpleNamespace, request: dict, respond_async: bool = False
) -> httpx.Response:
    headers = {
        **world.headers,
        **({"Prefer": "respond-async"} if respond_async else {}),
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=world.app), base_url="http://localhost"
    ) as client:
        return await client.post(
            "/api/interop/v1/messages",
            content=json.dumps(request),
            headers={**headers, "Content-Type": "application/json"},
        )


@pytest.mark.asyncio
async def test_native_descriptor_and_sdk_negotiation_do_not_claim_remote_service_support(
    world: SimpleNamespace,
) -> None:
    async def exchange(text: str) -> str:
        response = await send(world, json.loads(text))
        assert response.status_code == 200
        return response.text

    client = Client(exchange)
    negotiated = await client.negotiate(
        frame("negotiate.request", {"versions": ["1.0.0"], "requiredCapabilities": []})
    )
    assert negotiated["body"]["executionEnabled"] is False
    assert negotiated["body"]["capabilities"][0]["availability"] == "disabled"
    with pytest.raises(ContractError) as error:
        await client.call(read_request())
    assert error.value.code == "CAPABILITY_UNAVAILABLE"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=world.app), base_url="http://localhost"
    ) as http:
        response = await http.get("/api/interop/v1/descriptor", headers=world.headers)
    descriptor = validate(response.json())["body"]
    assert descriptor["appInstanceId"] == "native-instance"
    assert descriptor["trust"] == "unverified" and descriptor["endpoints"] == []
    assert descriptor["capabilities"][0]["availability"] == "disabled"


@pytest.mark.asyncio
async def test_inventory_is_not_fabricated_into_service_descriptors(
    world: SimpleNamespace,
) -> None:
    before = devices.list_devices()
    assert len(before) == 1
    calls = []
    original = native_api.list_devices

    def counted():
        calls.append(1)
        return original()

    world.monkeypatch.setattr(native_api, "list_devices", counted)
    response = (await send(world, read_request())).json()
    assert response["kind"] == "error" and response["body"]["code"] == "NO_ADAPTER"
    assert "output" not in response["body"] and calls == []
    assert devices.list_devices() == before


@pytest.mark.asyncio
async def test_native_auth_and_caller_grants_fail_closed(
    world: SimpleNamespace,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=world.app), base_url="http://localhost"
    ) as http:
        assert (
            await http.post("/api/interop/v1/messages", json=read_request())
        ).status_code == 401
    claim = read_request()
    claim["body"]["capabilityRef"] = {
        "issuer": "https://untrusted.example",
        "referenceId": "pretend-grant",
    }
    assert (await send(world, claim)).json()["body"]["code"] == "DENIED"
    execute = read_request()
    execute["body"]["mode"] = "execute"
    assert (await send(world, execute)).status_code == 400
    wrong_target = read_request()
    wrong_target["body"]["target"]["appInstanceId"] = "another-native-instance"
    assert (await send(world, wrong_target)).json()["body"][
        "code"
    ] == "BINDING_MISMATCH"


@pytest.mark.asyncio
async def test_real_native_session_revocation_denies_descriptor_and_query(
    world: SimpleNamespace,
) -> None:
    world.revoke()
    assert (await send(world, read_request())).status_code == 401
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=world.app), base_url="http://localhost"
    ) as http:
        assert (
            await http.get("/api/interop/v1/descriptor", headers=world.headers)
        ).status_code == 401


@pytest.mark.asyncio
async def test_native_generation_and_disable_are_rechecked(
    world: SimpleNamespace,
) -> None:
    world.monkeypatch.setenv(PREFIX + "_GENERATION", "2")
    request = read_request()
    response = (await send(world, request)).json()
    assert (
        response["generation"] == 2 and response["body"]["code"] == "STALE_GENERATION"
    )
    with pytest.raises(ContractError) as error:
        check_response(request, response)
    assert error.value.code == "STALE_GENERATION"
    world.monkeypatch.setenv(PREFIX + "_READ_ENABLED", "0")
    assert (await send(world, read_request(generation=2))).json()["body"][
        "code"
    ] == "FORBIDDEN"


def test_exact_vendored_candidate_has_recorded_schema_and_source_hashes() -> None:
    import interop_bridge

    root = Path(interop_bridge.__file__).parent
    manifest = json.loads((root / "SOURCE.json").read_text())
    assert manifest["commit"] == "cc9fed2027c81a43e69b74d923b7fd13cbdf6d81"
    for path, metadata in manifest["files"].items():
        assert (
            hashlib.sha256((root / path).read_bytes()).hexdigest() == metadata["sha256"]
        )
    assert (
        manifest["schemaSha256"]
        == manifest["files"]["_vendor/r_sdk_interop/schema.json"]["sha256"]
    )
