import pytest
from fastapi.testclient import TestClient

from core.auth import server_host
from main import app


@pytest.fixture(autouse=True)
def clear_access_environment(monkeypatch):
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    monkeypatch.delenv('R_LINK_HOST', raising=False)
    monkeypatch.delenv('R_LINK_CORS_ORIGINS', raising=False)


@pytest.mark.parametrize('peer', ['127.0.0.1', '::1'])
@pytest.mark.parametrize('origin', [None, 'http://127.0.0.1:4322', 'http://tauri.localhost', 'http://127.0.0.1:8210'])
def test_local_access_works_without_an_account(peer, origin):
    client = TestClient(app, base_url='http://127.0.0.1:8210', client=(peer, 50000))
    try:
        headers = {'Origin': origin} if origin else {}
        response = client.post('/api/auth/ws-token', headers=headers)
        assert response.status_code == 200
        assert response.json()['scope'] == 'ssh'
        assert response.json()['expires_in'] == 60
    finally:
        client.close()


@pytest.mark.parametrize('peer,host,headers', [
    ('192.0.2.2', '127.0.0.1', {}),
    ('127.0.0.1', 'rebound.example', {}),
    ('127.0.0.1', 'localhost', {'Origin': 'https://untrusted.example'}),
    ('127.0.0.1', 'localhost', {'Origin': 'null'}),
    ('127.0.0.1', 'localhost', {'Sec-Fetch-Site': 'cross-site'}),
    ('192.0.2.2', 'localhost', {'X-Forwarded-For': '127.0.0.1'}),
])
def test_local_mode_rejects_remote_and_cross_site_requests(peer, host, headers):
    client = TestClient(app, base_url=f'http://{host}:8210', client=(peer, 50000))
    try:
        assert client.post('/api/auth/ws-token', headers=headers).status_code == 401
    finally:
        client.close()


@pytest.mark.parametrize('key', [None, 'wrong', 'correct-service-key'])
def test_remote_access_requires_correct_key(monkeypatch, key):
    monkeypatch.setenv('R_LINK_API_TOKEN', 'correct-service-key')
    client = TestClient(app, base_url='https://api.example', client=('192.0.2.2', 50000))
    try:
        headers = {'Authorization': f'Bearer {key}'} if key else {}
        response = client.post('/api/auth/ws-token', headers=headers)
        assert response.status_code == (200 if key == 'correct-service-key' else 401)
    finally:
        client.close()


def test_configured_key_is_required_even_on_loopback(monkeypatch):
    monkeypatch.setenv('R_LINK_API_TOKEN', 'configured-key')
    client = TestClient(app, base_url='http://localhost:8210', client=('127.0.0.1', 50000))
    try:
        assert client.post('/api/auth/ws-token').status_code == 401
    finally:
        client.close()


def test_default_bind_is_local_and_remote_bind_requires_key(monkeypatch):
    assert server_host() == '127.0.0.1'
    monkeypatch.setenv('R_LINK_HOST', '0.0.0.0')
    with pytest.raises(RuntimeError):
        server_host()
    monkeypatch.setenv('R_LINK_API_TOKEN', 'configured-key')
    assert server_host() == '0.0.0.0'


@pytest.mark.parametrize('path', ['/session', '/me', '/logout', '/verify', '/refresh'])
def test_cloud_account_endpoints_are_removed(path):
    client = TestClient(app)
    try:
        assert client.get('/api/auth' + path).status_code == 404
        assert client.post('/api/auth' + path).status_code == 404
    finally:
        client.close()
