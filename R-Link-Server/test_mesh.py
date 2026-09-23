"""Real HTTP contract with an in-memory NetBird API, never a fabricated peer registry."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from api import mesh as mesh_api
from core.mesh import NetBird, PolicyInput, ResourceInput, RouterInput, SetupKeyInput
from main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 5555)) as value:
        yield value


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/mesh/status'), ('GET', '/api/mesh/peers'), ('DELETE', '/api/mesh/peers/one'),
    ('GET', '/api/mesh/groups'), ('POST', '/api/mesh/groups'), ('PUT', '/api/mesh/groups/one'),
    ('GET', '/api/mesh/setup-keys'), ('POST', '/api/mesh/setup-keys'),
    ('GET', '/api/mesh/policies'), ('POST', '/api/mesh/policies'),
    ('GET', '/api/mesh/networks'), ('POST', '/api/mesh/networks'),
    ('GET', '/api/mesh/networks/one/resources'), ('POST', '/api/mesh/networks/one/resources'),
    ('GET', '/api/mesh/networks/one/routers'), ('POST', '/api/mesh/networks/one/routers'),
])
def test_mesh_routes_require_r_link_auth(method, path):
    with TestClient(app) as remote:
        assert remote.request(method, path).status_code == 401


def test_unconfigured_mesh_is_explicit_and_never_invents_peers(client):
    status = client.get('/api/mesh/status')
    assert status.status_code == 200
    assert status.json()['configured'] is False
    assert status.json()['connected'] == 0
    assert client.get('/api/mesh/peers').status_code == 503


def configured(monkeypatch, handler):
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'private-pat')
    monkeypatch.setattr(mesh_api.netbird, 'transport', httpx.MockTransport(handler))


def test_peer_status_group_membership_and_one_time_key(client, monkeypatch):
    calls = []
    def handler(request):
        assert request.headers['Authorization'] == 'Token private-pat'
        assert request.url.host == 'mesh.example.test'
        calls.append((request.method, request.url.path, request.content))
        if request.url.path == '/api/peers':
            return httpx.Response(200, json=[{'id': 'peer01', 'name': 'nas', 'ip': '100.100.1.1',
                                              'connected': True, 'groups': [{'id': 'group01', 'name': 'private'}]}])
        if request.url.path == '/api/setup-keys':
            if request.method == 'POST':
                return httpx.Response(201, json={'id': 123, 'name': 'onboard', 'key': 'ONE-TIME-SECRET'})
            return httpx.Response(200, json=[{'id': 123, 'name': 'onboard', 'key': 'MASKED-SECRET'}])
        if request.url.path == '/api/groups/group01':
            if request.method == 'GET':
                return httpx.Response(200, json={'id': 'group01', 'name': 'private', 'resources': [{'id': 'resource01', 'type': 'host'}]})
            return httpx.Response(200, json={'id': 'group01', 'name': 'private'})
        return httpx.Response(200, json={'id': 'resource01'})
    configured(monkeypatch, handler)
    assert client.get('/api/mesh/status').json()['connected'] == 1
    peers = client.get('/api/mesh/peers').json()
    assert peers[0]['ip'] == '100.100.1.1'
    assert peers[0]['groups'][0]['name'] == 'private'
    created = client.post('/api/mesh/setup-keys', json={'name': 'onboard', 'auto_groups': ['group01']})
    assert created.status_code == 201
    assert created.json()['key'] == 'ONE-TIME-SECRET'
    assert created.headers['Cache-Control'] == 'no-store'
    listed = client.get('/api/mesh/setup-keys')
    assert 'key' not in listed.text
    changed = client.put('/api/mesh/groups/group01', json={'name': 'private', 'peers': ['peer01']})
    assert changed.status_code == 200
    body = json.loads(next(payload for method, path, payload in calls if method == 'PUT' and path == '/api/groups/group01'))
    assert body['resources'] == [{'id': 'resource01', 'type': 'host'}]
    assert body['peers'] == ['peer01']
    assert all('private-pat' not in str(event) for event in client.get('/api/audit').json())


def test_policy_resource_router_payloads_and_boundaries(client, monkeypatch):
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        return httpx.Response(201, json={'id': 'created01'})
    configured(monkeypatch, handler)
    policy = {'name': 'allow-ssh', 'source_group': 'group01', 'destination_group': 'group02',
              'protocol': 'tcp', 'ports': [22], 'enabled': True, 'bidirectional': False}
    assert client.post('/api/mesh/policies', json=policy).status_code == 201
    assert calls[-1][2]['rules'][0]['ports'] == ['22']
    assert calls[-1][2]['rules'][0]['sources'] == ['group01']
    assert client.post('/api/mesh/networks', json={'name': 'office', 'description': ''}).status_code == 201
    assert client.post('/api/mesh/networks/created01/resources', json={
        'name': 'lan', 'address': '192.168.1.0/24', 'groups': ['group02']}).status_code == 201
    assert calls[-1][2]['address'] == '192.168.1.0/24'
    assert client.post('/api/mesh/networks/created01/routers', json={'peer': 'peer01'}).status_code == 201
    assert calls[-1][2]['peer'] == 'peer01' and 'peer_groups' not in calls[-1][2]
    count = len(calls)
    assert client.post('/api/mesh/networks/created01/routers', json={'peer': 'peer01', 'peer_groups': ['group01']}).status_code == 422
    assert client.post('/api/mesh/policies', json=dict(policy, protocol='all', ports=[22])).status_code == 422
    assert client.post('/api/mesh/networks/created01/resources', json={'name': 'bad', 'address': '../etc/passwd', 'groups': ['group01']}).status_code == 422
    assert client.delete('/api/mesh/networks/../routers/one').status_code in (400, 404)
    assert len(calls) == count


def test_policy_edit_does_not_replace_an_unmanaged_policy(client, monkeypatch):
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == 'GET':
            return httpx.Response(200, json={'description': 'External policy', 'rules': [{'id': 'rule01'}]})
        return httpx.Response(200, json={'id': 'policy01'})
    configured(monkeypatch, handler)
    payload = {'name': 'allow-ssh', 'source_group': 'group01', 'destination_group': 'group02'}
    response = client.put('/api/mesh/policies/policy01', json=payload)
    assert response.status_code == 409
    assert calls == [('GET', '/api/policies/policy01')]


def test_r_link_policy_can_be_updated_without_leaking_unrelated_rules(client, monkeypatch):
    bodies = []
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'description': 'R-Link managed policy', 'rules': [
                {'id': 'rule01', 'sources': [{'id': 'group01'}], 'destinations': [{'id': 'group02'}]}
            ]})
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={'id': 'policy01'})
    configured(monkeypatch, handler)
    response = client.put('/api/mesh/policies/policy01', json={
        'name': 'allow-ssh', 'source_group': 'group01', 'destination_group': 'group02',
        'protocol': 'tcp', 'ports': [22], 'bidirectional': True,
    })
    assert response.status_code == 200
    assert bodies[0]['description'] == 'R-Link managed policy'
    assert bodies[0]['rules'][0]['bidirectional'] is True
    assert bodies[0]['rules'][0]['ports'] == ['22']


@pytest.mark.parametrize('value', ['http://api.example.com', 'https://u:p@example.com',
                                    'https://example.com/path', 'file:///etc/passwd'])
def test_management_url_requires_https_or_local_loopback(client, monkeypatch, value):
    monkeypatch.setenv('R_LINK_NETBIRD_URL', value)
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'private-pat')
    assert client.get('/api/mesh/peers').status_code == 503


def test_no_redirect_or_token_leak_on_upstream_error(client, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(302, headers={'Location': 'https://untrusted.example/steal'})
    configured(monkeypatch, handler)
    result = client.get('/api/mesh/peers')
    assert result.status_code == 502
    assert calls == ['mesh.example.test']
    assert 'private-pat' not in result.text


def test_models_reject_invalid_network_scope():
    with pytest.raises(Exception):
        RouterInput(peer='node', peer_groups=['group'])
    with pytest.raises(Exception):
        SetupKeyInput(name='bad', auto_groups=[])
    with pytest.raises(Exception):
        PolicyInput(name='bad', source_group='group01', destination_group='group02', protocol='all', ports=[22])
    with pytest.raises(Exception):
        ResourceInput(name='bad', address='../../secret', groups=['group'])
