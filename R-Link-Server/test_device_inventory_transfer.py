import pytest
from fastapi.testclient import TestClient
from core import devices
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(tmp_path / 'devices.sqlite'))
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    with TestClient(app, base_url='http://localhost:8210', client=('127.0.0.1', 55555)) as client:
        yield client


def test_import_normalizes_and_skips_duplicates_without_overwriting(client):
    payload = {'version': 1, 'devices': [
        {'name': 'original', 'host': 'NAS.EXAMPLE.', 'port': 22},
        {'name': 'duplicate', 'host': 'nas.example', 'port': 22},
        {'name': 'second service', 'host': 'nas.example', 'port': 80},
    ]}
    result = client.post('/api/devices/import', json=payload)
    assert result.status_code == 200
    assert result.json() == {'added': 2, 'skipped': 1}
    assert client.post('/api/devices/import', json=payload).json() == {'added': 0, 'skipped': 3}
    exported = client.get('/api/devices/export').json()
    assert exported['version'] == 1
    assert len(exported['devices']) == 2
    assert exported['devices'][0]['name'] == 'original'
    assert set(exported['devices'][0]) == {'name', 'host', 'port', 'username'}


@pytest.mark.parametrize('invalid', [
    {'name': 'invalid', 'host': '../bad'},
    {'name': 'invalid', 'host': 'host', 'password': 'must-not-store'},
    {'name': 'invalid', 'host': 'host', 'port': 99999},
])
def test_invalid_import_does_not_partially_write(client, invalid):
    result = client.post('/api/devices/import', json={'version': 1, 'devices': [{'name': 'valid', 'host': 'localhost'}, invalid]})
    assert result.status_code == 422
    assert devices.list_devices() == []


def test_capacity_failure_rolls_back_earlier_imported_rows(client):
    with devices.database() as db:
        db.executemany('INSERT INTO devices (id,name,host,port,username) VALUES (?,?,?,?,?)',
                       [(str(i), str(i), f'host{i}.example', 22, '') for i in range(255)])
    response = client.post('/api/devices/import', json={'devices': [
        {'name': 'first', 'host': 'first.example'}, {'name': 'overflow', 'host': 'last.example'},
    ]})
    assert response.status_code == 409
    assert len(devices.list_devices()) == 255
    assert not any(d['host'] == 'first.example' for d in devices.list_devices())


def test_transfer_endpoints_reject_anonymous_remote_requests():
    with TestClient(app) as client:
        assert client.get('/api/devices/export').status_code == 401
        assert client.post('/api/devices/import', json={'devices': []}).status_code == 401
