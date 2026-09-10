"""Local HTTP/WS boundary checks; no provider login, plugins or SSH are started."""
import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.supabase_auth import auth_manager
from main import app
from api import ssh as ssh_api


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/plugins/"),
    ("GET", "/api/system/info"),
    ("POST", "/api/console/start"),
    ("GET", "/api/ssh/connections"),
    ("POST", "/api/ssh/connections/missing/close"),
    ("POST", "/api/auth/ws-token"),
])
def test_management_endpoints_reject_anonymous_requests(method, path):
    # No context manager: do not run app lifespan / plugin discovery.
    client = TestClient(app)
    try:
        assert client.request(method, path).status_code == 401
    finally:
        client.close()


@pytest.mark.parametrize("scope", [None, "console"])
def test_websocket_rejects_missing_or_wrong_scope(scope):
    protocols = ["r-link.ssh"]
    if scope:
        token = asyncio.run(auth_manager.issue_websocket_token({"id": "test-user"}, scope=scope, ttl_seconds=60))
        protocols.append(f"r-link.ssh-token.{token}")
    client = TestClient(app)
    try:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/api/ssh/connect?host=unused.invalid&username=test", subprotocols=protocols):
                pytest.fail("Unauthenticated websocket accepted")
        assert error.value.code == 1008
    finally:
        client.close()


def test_scoped_websocket_handshake_and_cleanup_without_ssh(monkeypatch):
    async def forbidden_connection(*args, **kwargs):
        pytest.fail("A real SSH connection must never start in this test")
    monkeypatch.setattr(ssh_api.SSHConnection, "connect", forbidden_connection)
    token = asyncio.run(auth_manager.issue_websocket_token({"id": "test-user"}, scope="ssh", ttl_seconds=60))
    client = TestClient(app)
    try:
        with client.websocket_connect("/api/ssh/connect?host=unused.invalid&username=test", subprotocols=["r-link.ssh", f"r-link.ssh-token.{token}"]) as ws:
            assert ws.accepted_subprotocol == "r-link.ssh"
            # Rejecting a non-auth first message exercises teardown without SSH.
            ws.send_json({"type": "close"})
            assert ws.receive_json()["type"] == "error"
        assert not ssh_api.active_connections
    finally:
        client.close()


def test_dynamic_plugin_and_api_share_connection_registry():
    import importlib.util
    from pathlib import Path
    from api import ssh as ssh_api

    spec = importlib.util.spec_from_file_location(
        "webssh_plugin_contract_test", Path(__file__).parent / "builtin/webssh-plugin/__init__.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Plugin({}).manager is ssh_api.get_connection_manager()


def test_websocket_signing_secret_never_uses_public_anon_key(monkeypatch):
    from core import supabase_auth

    monkeypatch.delenv("R_LINK_WS_TOKEN_SECRET", raising=False)
    monkeypatch.setattr(supabase_auth, "SUPABASE_ANON_KEY", "public-anon-key")
    first, second = supabase_auth.SupabaseAuth(), supabase_auth.SupabaseAuth()
    try:
        assert first.websocket_secret != "public-anon-key"
        assert first.websocket_secret != second.websocket_secret
        monkeypatch.setenv("R_LINK_WS_TOKEN_SECRET", "configured-server-secret")
        configured = supabase_auth.SupabaseAuth()
        try:
            assert configured.websocket_secret == "configured-server-secret"
        finally:
            asyncio.run(configured.close())
    finally:
        asyncio.run(first.close())
        asyncio.run(second.close())
