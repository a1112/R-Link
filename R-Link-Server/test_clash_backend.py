import os
import stat
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.clash import (
    ClashManager,
    ProxySelection,
    _normalize_managed_config,
    _profile_config,
    encoded_path_name,
    sanitize_connection,
    sanitize_provider,
)
from core.service_state import ServiceState
from main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("R_LINK_API_TOKEN", raising=False)
    with TestClient(app, base_url="http://localhost:8210", client=("127.0.0.1", 55555)) as value:
        yield value


def test_clash_endpoints_are_authenticated_and_settings_redact_secret(client, monkeypatch):
    assert client.get("/api/clash/settings", headers={"Origin": "https://evil.invalid"}).status_code == 401

    assert client.put("/api/clash/settings", json={"controller_url": "http://192.0.2.3:9090"}).status_code == 422
    assert client.put("/api/clash/settings", json={"controller_url": "https://controller.example:443"}).status_code == 422
    response = client.put("/api/clash/settings", json={"controller_url": "https://controller.example:443", "secret": "private-controller-key"})
    assert response.status_code == 200
    assert response.json() == {"controller_url": "https://controller.example", "has_secret": True}
    assert "private-controller-key" not in response.text
    assert "private-controller-key" not in client.get("/api/clash/settings").text


@pytest.mark.asyncio
async def test_controller_path_names_are_encoded_and_responses_are_sanitized(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager._managed_target = {"controller_url": "http://127.0.0.1:9090", "secret": "private"}
    manager._response = AsyncMock()
    await manager.select_proxy("香港 / 自动", ProxySelection(name="节点 / 一"))
    assert manager._response.call_args.args == ("PUT", "/proxies/%E9%A6%99%E6%B8%AF%20%2F%20%E8%87%AA%E5%8A%A8")
    assert manager._response.call_args.kwargs["json_body"] == {"name": "节点 / 一"}

    connection = sanitize_connection({
        "id": "secret-id",
        "upload": 2,
        "download": 3,
        "rule": "MATCH",
        "rulePayload": "private-node-password",
        "metadata": {"host": "example.com", "process": "private-process", "sourcePort": "123"},
        "chains": ["DIRECT"],
    })
    assert "process" not in connection["metadata"]
    assert "rulePayload" not in connection
    provider = sanitize_provider({"name": "sub", "type": "Proxy", "vehicleType": "HTTP", "url": "https://secret.invalid/sub"})
    assert "url" not in provider


def test_profile_parser_rejects_recursive_alias_and_normalizes_side_effects(tmp_path):
    with pytest.raises(Exception, match="递归"):
        _profile_config("a: &a\n  nested: *a\n")
    normalized = _normalize_managed_config(
        {"tun": {"enable": True}, "dns": {"enable": True, "listen": "0.0.0.0:53"},
         "listeners": [{"name": "inbound"}], "proxy-providers": {"sub/x": {"path": "/etc/passwd"}}},
        "http://127.0.0.1:10999", "generated-secret", tmp_path, 12345,
    )
    assert normalized["external-controller"] == "127.0.0.1:10999"
    assert normalized["tun"]["enable"] is False
    assert normalized["dns"]["enable"] is False
    assert "listen" not in normalized["dns"]
    assert "listeners" not in normalized
    assert normalized["mixed-port"] == 12345
    assert normalized["proxy-providers"]["sub/x"]["path"].startswith(str(tmp_path))
    assert encoded_path_name("node%20literal") == "node%2520literal"
    first = _normalize_managed_config({"proxy-providers": {"中文": {}}}, "http://127.0.0.1:1", "x", tmp_path)
    second = _normalize_managed_config({"proxy-providers": {"中文!": {}}}, "http://127.0.0.1:1", "x", tmp_path)
    assert first["proxy-providers"]["中文"]["path"] != second["proxy-providers"]["中文!"]["path"]


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="shell fixture is POSIX-only")
async def test_owned_process_is_stopped_only_through_managed_handle(tmp_path, monkeypatch):
    binary = tmp_path / "mihomo-fixture"
    binary.write_text("#!/bin/sh\nfor arg in \"$@\"; do [ \"$arg\" = \"-t\" ] && exit 0; done\nsleep 30\n")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("R_LINK_MIHOMO_BINARY", str(binary))
    manager = ClashManager(ServiceState(tmp_path / "state"))
    profile = await manager.save_profile(type("Input", (), {"name": "fixture", "content": "mode: rule\n"})())
    try:
        result = await manager.start_managed(profile["id"])
        assert result["profile_id"] == profile["id"]
        assert manager.managed_status()["state"] == "running"
        config = manager.process.directory / "mihomo.yaml"
        assert "external-controller: 127.0.0.1:" in config.read_text()
        await manager.stop_managed()
        assert manager.managed_status()["state"] == "stopped"
    finally:
        await manager.close()
