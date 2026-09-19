import asyncio
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from core import devices
from api import devices as device_api, system, ssh
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("R_LINK_DEVICES_DB", str(tmp_path / "devices.sqlite3"))
    monkeypatch.delenv("R_LINK_API_TOKEN", raising=False)
    with TestClient(app, base_url="http://localhost:8210", client=("127.0.0.1", 55555)) as client:
        yield client


def test_inventory_crud_persists_and_normalizes_duplicates(client):
    payload = {"name": "NAS", "host": "NAS.EXAMPLE.", "port": 22, "username": "admin"}
    response = client.post('/api/devices', json=payload)
    assert response.status_code == 201
    device = response.json()
    assert device['host'] == 'nas.example'
    assert devices.list_devices() == [device]  # separate database connection
    assert client.post('/api/devices', json=payload).status_code == 409
    updated = client.put('/api/devices/' + device['id'], json={**payload, 'port': 2222}).json()
    assert updated['revision'] == 2
    assert updated['status'] == 'unchecked'
    assert client.delete('/api/devices/' + device['id']).status_code == 204
    assert client.get('/api/devices').json() == []
    assert client.delete('/api/devices/' + device['id']).status_code == 404


@pytest.mark.parametrize('fields', [
    {'host': 'https://host/path'}, {'host': 'host; whoami'}, {'host': '0.0.0.0'},
    {'host': '224.0.0.1'}, {'host': '../file'}, {'port': 0}, {'port': 65536},
    {'port': 22.5}, {'name': '   '}, {'password': 'must-not-store'},
])
def test_inventory_rejects_invalid_targets_and_credentials(client, fields):
    assert client.post('/api/devices', json={'name': 'test', 'host': 'localhost', **fields}).status_code == 422


def test_inventory_denies_anonymous_remote_management():
    with TestClient(app) as client:
        assert client.get('/api/devices').status_code == 401
        assert client.get('/api/system/network').status_code == 401
        assert client.post('/api/devices/id/probe').status_code == 401


@pytest.mark.asyncio
async def test_probe_real_loopback_service_and_connection_refused(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(tmp_path / 'devices.db'))
    async def accept(reader, writer):
        await reader.read()
        writer.close()
        await writer.wait_closed()
    server = await asyncio.start_server(accept, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    device = devices.save_device(devices.DeviceInput(name='local fixture', host='127.0.0.1', port=port))
    try:
        result = await device_api.probe_device(device['id'])
        assert result['status'] == 'reachable'
        assert result['latency_ms'] >= 0 and result['checked_at']
    finally:
        server.close()
        await server.wait_closed()
    result = await device_api.probe_device(device['id'])
    assert result['status'] == 'unreachable' and result['latency_ms'] is None
    assert not device_api._inflight


@pytest.mark.asyncio
async def test_stale_probe_cannot_overwrite_edited_device(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(tmp_path / 'devices.db'))
    old = devices.save_device(devices.DeviceInput(name='test', host='host.example'))
    edited = devices.save_device(devices.DeviceInput(name='test', host='other.example'), old['id'])
    result = devices.record_probe(old, True, 1)
    assert result == edited
    devices.delete_device(old['id'])
    with pytest.raises(HTTPException):
        devices.record_probe(old, True, 1)
    assert devices.list_devices() == []


@pytest.mark.asyncio
async def test_cancelled_probe_releases_slot(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(tmp_path / 'devices.db'))
    device = devices.save_device(devices.DeviceInput(name='test', host='host.example'))
    entered = asyncio.Event()
    async def blocked(*args):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(device_api.asyncio, 'open_connection', blocked)
    task = asyncio.create_task(device_api.probe_device(device['id']))
    await asyncio.wait_for(entered.wait(), 2)
    with pytest.raises(HTTPException) as error:
        await device_api.probe_device(device['id'])
    assert error.value.status_code == 429
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not device_api._inflight


def test_network_snapshot_uses_actual_interface_counters(monkeypatch):
    monkeypatch.setattr(system.psutil, 'net_io_counters', lambda **kw: {'eth0': SimpleNamespace(bytes_sent=100, bytes_recv=200)})
    monkeypatch.setattr(system.psutil, 'net_if_stats', lambda: {'eth0': SimpleNamespace(isup=True)})
    monkeypatch.setattr(system.psutil, 'net_if_addrs', lambda: {'eth0': [SimpleNamespace(family=socket.AF_INET, address='192.0.2.10')]})
    result = system.get_network()
    assert result['interfaces'] == [{'name': 'eth0', 'is_up': True, 'addresses': ['192.0.2.10'], 'bytes_sent': 100, 'bytes_recv': 200}]


@pytest.mark.asyncio
async def test_failed_websocket_accept_does_not_leak_connection_slot(monkeypatch):
    monkeypatch.setattr(ssh, '_authenticate_websocket', AsyncMock(return_value=True))
    ws = SimpleNamespace(scope={'subprotocols': []}, accept=AsyncMock(side_effect=RuntimeError('peer left')))
    count = ssh.get_connection_manager().get_connection_count()
    with pytest.raises(RuntimeError):
        await ssh.ssh_websocket(ws, 'localhost', 22, 'test')
    assert ssh.get_connection_manager().get_connection_count() == count
