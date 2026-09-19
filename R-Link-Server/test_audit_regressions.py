import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import zipfile

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from api import plugins, ssh
from core.plugin_packages import install_zip, plugin_path
from core.plugin_manager import PluginManager, BinaryPlugin
from core.plugin_interface import PluginStatus
from core.python_plugin import PythonPlugin
from core.supabase_auth import auth_manager, require_admin, require_auth
from main import app


@pytest.mark.asyncio
async def test_user_metadata_cannot_grant_administrator(monkeypatch):
    monkeypatch.delenv("R_LINK_ADMIN_USER_IDS", raising=False)
    with pytest.raises(HTTPException) as error:
        await require_admin({"id": "user", "user_metadata": {"role": "admin"}})
    assert error.value.status_code == 403
    assert await require_admin({"id": "admin", "app_metadata": {"role": "admin"}})
    monkeypatch.setenv("R_LINK_ADMIN_USER_IDS", "first, user")
    assert await require_admin({"id": "user"})


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/plugins/reload"), ("POST", "/api/plugins/install/url"),
    ("DELETE", "/api/plugins/uninstall"), ("POST", "/api/console/start"),
    ("GET", "/api/plugin-sources/"),
])
def test_regular_users_cannot_manage_server(method, path):
    app.dependency_overrides[require_auth] = lambda: {"id": "ordinary-user"}
    try:
        client = TestClient(app)
        try:
            assert client.request(method, path, json={}).status_code == 403
        finally:
            client.close()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("name", ["..", "../outside", "a/b", "a\\b", "C:\\outside", "temp", "NUL", "x:y"])
def test_plugin_names_cannot_escape_root(tmp_path, name):
    with pytest.raises(HTTPException):
        plugin_path(tmp_path, name)


def write_package(path, prefix="", name="demo", manifest="manifest.yaml"):
    with zipfile.ZipFile(path, "w") as archive:
        text = f'name: {name}\nentry: __init__.py\n' if manifest.endswith("yaml") else '{"name":"demo","entry":"__init__.py"}'
        archive.writestr(prefix + manifest, text)
        archive.writestr(prefix + "__init__.py", "# fixture\n")


@pytest.mark.parametrize("prefix", ["", "download-folder/"])
def test_root_and_nested_packages_install_by_manifest_name(tmp_path, prefix):
    package = tmp_path / "plugin.zip"
    write_package(package, prefix)
    root = tmp_path / "plugins"
    assert install_zip(package, root) == "demo"
    assert (root / "demo/__init__.py").is_file()
    with pytest.raises(HTTPException) as error:
        install_zip(package, root)
    assert error.value.status_code == 409
    assert (root / "demo/__init__.py").read_text() == "# fixture\n"


@pytest.mark.asyncio
async def test_upload_path_rejected_without_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(plugins, "plugin_manager", SimpleNamespace(plugins_dir=str(tmp_path / "plugins")))
    with pytest.raises(HTTPException) as error:
        await plugins.install_plugin_upload(UploadFile(filename="../outside.py", file=BytesIO(b"bad")))
    assert error.value.status_code == 400
    assert not (tmp_path / "outside.py").exists()


def test_binary_plugin_not_overwritten_and_unloaded_python_not_running(tmp_path):
    root = tmp_path / "plugins"
    binary = root / "binary"
    binary.mkdir(parents=True)
    (binary / "manifest.yaml").write_text("name: binary\nversion: '1'\ndescription: test\nauthor: test\nbinary: test.exe\n")
    (binary / "helper.py").write_text("# must not turn binary into a Python plugin")
    package = tmp_path / "python.zip"
    write_package(package, manifest="manifest.json")
    install_zip(package, root)
    manager = PluginManager(str(root), str(tmp_path / "builtin"))
    try:
        assert isinstance(manager.get_plugin("binary"), BinaryPlugin)
        assert isinstance(manager.get_plugin("demo"), PythonPlugin)
        assert manager.get_plugin_status("demo").status == PluginStatus.STOPPED
        assert manager.get_all_statuses()["demo"].status == PluginStatus.STOPPED
    finally:
        manager.cleanup()


@pytest.mark.asyncio
async def test_reload_keeps_shared_manager(tmp_path, monkeypatch):
    manager = PluginManager(str(tmp_path / "plugins"), str(tmp_path / "builtin"))
    monkeypatch.setattr(plugins, "plugin_manager", manager)
    from api import console
    monkeypatch.setattr(console, "_plugin_manager", manager)
    await plugins._reload_plugin_manager()
    assert plugins.plugin_manager is console._plugin_manager is manager
    manager.cleanup()


@pytest.mark.asyncio
async def test_ssh_connect_uses_process_api_and_no_server_credentials(monkeypatch):
    import asyncssh
    process = SimpleNamespace(stdin=Mock(), stdout=SimpleNamespace(read=AsyncMock(return_value="")), stderr=Mock())
    client = SimpleNamespace(create_process=AsyncMock(return_value=process), close=Mock(), wait_closed=AsyncMock())
    connect = AsyncMock(return_value=client)
    monkeypatch.setattr(asyncssh, "connect", connect)
    ws = SimpleNamespace(send_json=AsyncMock(), close=AsyncMock())
    conn = ssh.SSHConnection("session", ws, "example.invalid", 22, "test")
    assert await conn.connect(password="test", columns=100, rows=35)
    client.create_process.assert_awaited_once_with(term_type="xterm-256color", term_size=(100, 35))
    assert connect.call_args.kwargs["client_keys"] == []
    assert connect.call_args.kwargs["agent_path"] is None
    assert connect.call_args.kwargs.get("known_hosts", "default") is not None
    # EOF invokes close from the reader itself, which must not cancel/await itself.
    await asyncio.wait_for(conn.read_task, 1)
    assert conn.closed
    client.close.assert_called_once()
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_ssh_connection_owner_isolation():
    conn = ssh.SSHConnection("owned", SimpleNamespace(close=AsyncMock()), "host", 22, "root")
    conn.owner_id = "alice"
    ssh.active_connections["owned"] = conn
    ssh.get_connection_manager().create_connection("owned", "host", 22, "root")
    try:
        assert (await ssh.list_connections({"id": "bob"}))["count"] == 0
        assert (await ssh.list_connections({"id": "alice"}))["count"] == 1
        with pytest.raises(HTTPException) as error:
            await ssh.close_connection("owned", {"id": "bob"})
        assert error.value.status_code == 404
        assert not conn.closed
        await ssh.close_connection("owned", {"id": "alice"})
        assert not ssh.get_connection_manager().get_connection("owned")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_ticket_expiry_boundary_and_malformed_payload(monkeypatch):
    monkeypatch.setattr("core.supabase_auth.time.time", lambda: 1000)
    token = await auth_manager.issue_websocket_token({"id": "u"}, scope="ssh", ttl_seconds=0)
    assert await auth_manager.verify_websocket_token(token, expected_scope="ssh") is None
    assert await auth_manager.verify_websocket_token("闈炴硶.payload", expected_scope="ssh") is None
    assert await auth_manager.verify_websocket_token(auth_manager._encode_websocket_token([]), expected_scope="ssh") is None


def test_ttyd_start_uses_executable_path_and_loopback(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ttyd_regression", Path(__file__).parent / "builtin/ttyd-console/__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manager = module.TTYDManager(str(tmp_path))
    executable = tmp_path / "ttyd.exe"
    monkeypatch.setattr(manager, "is_running", lambda: False)
    monkeypatch.setattr(manager, "_find_ttyd", lambda: executable)
    monkeypatch.setattr(manager, "_is_port_available", lambda port: True)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    process = Mock(pid=123, poll=Mock(return_value=None))
    spawn = Mock(return_value=process)
    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    result = manager.start()
    assert result["success"]
    args = spawn.call_args.args[0]
    assert args[0] == str(executable)
    assert args[args.index("-i") + 1] == "127.0.0.1"
    assert spawn.call_args.kwargs["cwd"] == str(tmp_path)
    assert not manager.enable_nginx_proxy
