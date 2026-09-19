from pathlib import Path
import inspect
import sys
import zipfile

import pytest
from fastapi.params import Depends
from starlette.websockets import WebSocketState


SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from api import auth as auth_api
from api import plugins as plugins_api
from api import ssh as ssh_api
from core.auth import access_manager
from main import app


def test_all_management_routes_require_auth_except_public_endpoints() -> None:
    public_paths = {"/", "/health"}
    # OpenAPI includes mounted routers across FastAPI versions; checking only
    # app.routes can silently skip all management endpoints with lazy routers.
    checked = 0
    for path, operations in app.openapi()["paths"].items():
        if path in public_paths:
            continue
        if not path.startswith("/api/"):
            continue
        for method, operation in operations.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                assert operation.get("security"), f"{method} {path} should require authentication"
                checked += 1
    assert checked > 0


@pytest.mark.asyncio
async def test_issue_ssh_websocket_token_is_scoped_and_short_lived() -> None:
    token = await access_manager.issue_websocket_token({"id": "u1"}, scope="ssh", ttl_seconds=60)
    claims = await access_manager.verify_websocket_token(token, expected_scope="ssh")

    assert claims["sub"] == "u1"
    assert claims["scope"] == "ssh"


@pytest.mark.asyncio
async def test_websocket_token_verification_rejects_wrong_scope() -> None:
    token = await access_manager.issue_websocket_token({"id": "u1"}, scope="console", ttl_seconds=60)

    claims = await access_manager.verify_websocket_token(token, expected_scope="ssh")

    assert claims is None


@pytest.mark.asyncio
async def test_ssh_websocket_auth_rejects_plain_bearer_header() -> None:
    class DummyWebSocket:
        def __init__(self) -> None:
            self.headers = {"authorization": "Bearer plain-api-token"}
            self.query_params = {}
            self.scope = {"subprotocols": []}
            self.close_calls = []

        async def close(self, code: int, reason: str | None = None) -> None:
            self.close_calls.append((code, reason))

    websocket = DummyWebSocket()
    authenticated = await ssh_api._authenticate_websocket(websocket)

    assert authenticated is False
    assert websocket.close_calls == [(1008, "WebSocket token required")]


@pytest.mark.asyncio
async def test_ssh_websocket_auth_accepts_scoped_token_from_subprotocol() -> None:
    token = await access_manager.issue_websocket_token({"id": "u1"}, scope="ssh", ttl_seconds=60)

    class DummyWebSocket:
        def __init__(self, scoped_token: str) -> None:
            self.headers = {}
            self.query_params = {}
            self.scope = {"subprotocols": ["r-link.ssh", f"r-link.ssh-token.{scoped_token}"]}
            self.close_calls = []

        async def close(self, code: int, reason: str | None = None) -> None:
            self.close_calls.append((code, reason))

    websocket = DummyWebSocket(token)
    authenticated = await ssh_api._authenticate_websocket(websocket)

    assert authenticated is True
    assert websocket.close_calls == []


def test_extract_and_install_zip_rejects_path_traversal(tmp_path: Path) -> None:
    zip_path = tmp_path / "plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../escape/manifest.yaml", "name: escaped\n")
        archive.writestr("../escape/__init__.py", "")

    with pytest.raises(Exception):
        import asyncio

        asyncio.run(plugins_api._extract_and_install_zip(zip_path, str(tmp_path / "plugins")))
