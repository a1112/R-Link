"""Real control/relay authorization and concurrent one-off allocation regression tests."""
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import secrets
import time
import uuid

import anyio
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from api.fabric import relay
from core import fabric, identity, devices, fabric_inventory
from main import app


@pytest.fixture(autouse=True)
def isolated_fabric(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_FABRIC_DB', str(tmp_path / 'fabric.sqlite'))
    monkeypatch.setenv('R_LINK_FABRIC_PUBLIC_URL', 'https://fabric.example/r-link')
    monkeypatch.setenv('R_LINK_FABRIC_ADDRESS_POOL', '10.253.199.0/24')
    monkeypatch.setenv('R_LINK_API_TOKEN', 'fabric-test-admin-key')
    monkeypatch.delenv('R_LINK_AUTH_MODE', raising=False)
    monkeypatch.delenv('R_LINK_OIDC_ISSUER', raising=False)
    fabric.relay.invalidate_all()
    yield
    fabric.relay.invalidate_all()


ADMIN = {'Authorization': 'Bearer fabric-test-admin-key'}


def public_key():
    return base64.b64encode(secrets.token_bytes(32)).decode()


def direct_enroll(name='test-peer', groups=None):
    key = fabric.create_enrollment(fabric.EnrollmentInput(name='test', groups=groups or [fabric.DEFAULT_GROUP]), 'admin')
    peer = fabric.enroll(fabric.Enroll(enrollment_token=key['enrollment_token'], name=name, public_key=public_key(), os='Test OS'))
    return peer


def token_headers(peer):
    return {'Authorization': 'Bearer ' + peer['device_token']}


def test_enrollment_has_one_use_and_persists_only_credential_hashes():
    with TestClient(app) as client:
        issued = client.post('/api/fabric/enrollments', json={'name': 'one-off'}, headers=ADMIN)
        assert issued.status_code == 201
        token = issued.json()['enrollment_token']
        body = {'enrollment_token': token, 'name': 'peer-a', 'os': 'Test OS', 'public_key': public_key(), 'udp_port': 51820}
        response = client.post('/api/fabric/enrollment', json=body)
        assert response.status_code == 201
        peer = response.json()
        assert uuid.UUID(peer['peer_id']) and peer['virtual_ip'] == '10.253.199.1'
        assert client.post('/api/fabric/enrollment', json=dict(body, public_key=public_key())).status_code == 401
        metadata = client.get('/api/fabric/enrollments', headers=ADMIN)
        assert 'enrollment_token' not in metadata.text
        with fabric.database() as db:
            dump = ''.join(db.iterdump())
            assert token not in dump and peer['device_token'] not in dump
        assert response.headers['Cache-Control'] == 'no-store'


def test_parallel_unique_ip_allocation_and_single_enrollment_consumption():
    def enroll_unique(index):
        return direct_enroll('peer-' + str(index))['virtual_ip']
    with ThreadPoolExecutor(max_workers=8) as workers:
        addresses = list(workers.map(enroll_unique, range(16)))
    assert len(set(addresses)) == 16
    issued = fabric.create_enrollment(fabric.EnrollmentInput(name='race'), 'admin')
    def race(_):
        try:
            fabric.enroll(fabric.Enroll(enrollment_token=issued['enrollment_token'], name='race', public_key=public_key()))
            return 201
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(race, range(8)))
    assert results.count(201) == 1 and results.count(401) == 7


def test_expired_or_revoked_enrollment_cannot_register():
    issued = fabric.create_enrollment(fabric.EnrollmentInput(name='expired'), 'admin')
    with fabric.database() as db:
        db.execute('UPDATE fabric_enrollments SET expires_at=0')
    with pytest.raises(HTTPException) as failure:
        fabric.enroll(fabric.Enroll(enrollment_token=issued['enrollment_token'], name='test', public_key=public_key()))
    assert failure.value.status_code == 401
    issued = fabric.create_enrollment(fabric.EnrollmentInput(name='revoked'), 'admin')
    fabric.revoke_enrollment(issued['id'], 'admin')
    with pytest.raises(HTTPException) as failure:
        fabric.enroll(fabric.Enroll(enrollment_token=issued['enrollment_token'], name='test', public_key=public_key()))
    assert failure.value.status_code == 401


def test_configuration_failure_does_not_consume_enrollment(monkeypatch):
    issued = fabric.create_enrollment(fabric.EnrollmentInput(name='valid'), 'admin')
    monkeypatch.setenv('R_LINK_FABRIC_PUBLIC_URL', 'http://untrusted.example')
    with pytest.raises(HTTPException) as failure:
        fabric.enroll(fabric.Enroll(enrollment_token=issued['enrollment_token'], name='test', public_key=public_key()))
    assert failure.value.status_code == 503
    assert fabric.list_enrollments()[0]['used'] == 0


def test_machine_routes_never_accept_master_key_cookie_or_loopback():
    with TestClient(app, base_url='http://127.0.0.1:8210', client=('127.0.0.1', 40000)) as client:
        for headers in ({}, ADMIN, {'Cookie': '__Secure-r_link_session=pretend-admin'}):
            assert client.get('/api/fabric/agent/config', headers=headers).status_code == 401
            assert client.post('/api/fabric/agent/heartbeat', headers=headers, json={}).status_code == 401


def test_config_same_group_pair_secret_and_revocation():
    alice, bob = direct_enroll('alice'), direct_enroll('bob')
    outside = fabric.save_group(fabric.GroupInput(name='other'), 'admin')
    charlie = direct_enroll('charlie', [outside['id']])
    aconfig = fabric.agent_config(alice['peer_id'])
    bconfig = fabric.agent_config(bob['peer_id'])
    assert len(aconfig['peers']) == 1 and aconfig['peers'][0]['peer_id'] == bob['peer_id']
    assert len(base64.b64decode(aconfig['peers'][0]['pair_secret'])) == 32
    assert aconfig['peers'][0]['pair_secret'] == bconfig['peers'][0]['pair_secret']
    assert fabric.agent_config(charlie['peer_id'])['peers'] == []
    assert aconfig['relay_url'] == 'wss://fabric.example/r-link/api/fabric/relay'
    before = aconfig['config_version']
    fabric.revoke_peer(bob['peer_id'], 'admin')
    assert fabric.agent_config(alice['peer_id'])['peers'] == []
    assert fabric.agent_config(alice['peer_id'])['config_version'] > before
    with pytest.raises(HTTPException):
        fabric.machine(bob['device_token'])


def test_group_removal_rotates_pair_secret_and_isolation():
    alice, bob = direct_enroll('alice'), direct_enroll('bob')
    old = fabric.agent_config(alice['peer_id'])['peers'][0]['pair_secret']
    group = fabric.save_group(fabric.GroupInput(name='isolated'), 'admin')
    fabric.update_peer(bob['peer_id'], fabric.PeerUpdate(groups=[group['id']]), 'admin')
    assert not fabric.allowed_pair(alice['peer_id'], bob['peer_id'])
    fabric.update_peer(bob['peer_id'], fabric.PeerUpdate(groups=[fabric.DEFAULT_GROUP]), 'admin')
    assert fabric.agent_config(alice['peer_id'])['peers'][0]['pair_secret'] != old


def test_no_fabric_online_or_vpn_claim_until_actual_heartbeat_and_handshake():
    alice, bob = direct_enroll('alice'), direct_enroll('bob')
    assert not any(peer['connected'] for peer in fabric.list_peers())
    fabric.heartbeat(alice['peer_id'], fabric.Heartbeat(tunnel_ready=False, mode='transport-test',
                      peer_status=[fabric.PeerStatus(peer_id=bob['peer_id'], path='relay', rtt_ms=5)]))
    peer = next(peer for peer in fabric.list_peers() if peer['peer_id'] == alice['peer_id'])
    assert peer['control_connected'] and not peer['data_plane_confirmed']
    assert fabric.status()['mode_transport'] == 'transport-test'
    assert fabric.status()['capabilities']['vpn'] is False
    fabric.heartbeat(alice['peer_id'], fabric.Heartbeat(tunnel_ready=True, mode='vpn',
                      peer_status=[fabric.PeerStatus(peer_id=bob['peer_id'], path='direct', last_handshake=int(time.time()))]))
    peer = next(peer for peer in fabric.list_peers() if peer['peer_id'] == alice['peer_id'])
    assert peer['data_plane_confirmed'] and fabric.status()['capabilities']['vpn']
    with fabric.database() as db:
        db.execute('UPDATE fabric_peers SET last_seen=0 WHERE id=?', (alice['peer_id'],))
    peer = next(peer for peer in fabric.list_peers() if peer['peer_id'] == alice['peer_id'])
    assert not peer['connected'] and not peer['data_plane_confirmed'] and peer['paths'] == []


def test_candidate_telemetry_is_checked_and_config_version_changes():
    alice = direct_enroll('alice')
    before = fabric.agent_config(alice['peer_id'])['config_version']
    result = fabric.heartbeat(alice['peer_id'], fabric.Heartbeat(candidates=[fabric.Candidate(ip='192.168.10.15', port=52000)]))
    assert result['config_version'] > before
    assert fabric.heartbeat(alice['peer_id'], fabric.Heartbeat(candidates=[fabric.Candidate(ip='192.168.10.15', port=52000)]))['config_version'] == result['config_version']
    with TestClient(app) as client:
        assert client.post('/api/fabric/agent/heartbeat', headers=token_headers(alice), json={
            'candidates': [{'ip': '127.0.0.1', 'port': 52000}]}).status_code == 422
        assert client.post('/api/fabric/agent/heartbeat', headers=token_headers(alice), json={
            'peer_status': [{'peer_id': str(uuid.uuid4()), 'path': 'direct'}]}).status_code == 403


def test_relay_forwards_opaque_bytes_and_injects_only_authenticated_source():
    alice, bob = direct_enroll('alice'), direct_enroll('bob')
    payload = secrets.token_bytes(300)
    with TestClient(app) as client:
        with client.websocket_connect('/api/fabric/relay', headers=token_headers(bob)) as recipient:
            with client.websocket_connect('/api/fabric/relay', headers=token_headers(alice)) as source:
                source.send_bytes(uuid.UUID(bob['peer_id']).bytes + payload)
                received = recipient.receive_bytes()
                assert received[:16] == uuid.UUID(alice['peer_id']).bytes
                assert received[16:] == payload
                assert fabric.relay.connected(alice['peer_id'])
    assert not fabric.relay.connected(alice['peer_id'])


@pytest.mark.asyncio
@pytest.mark.parametrize('close_blocks', [False, True])
async def test_relay_cancellation_drains_owned_tasks_before_returning(monkeypatch, close_blocks):
    peer = direct_enroll()
    incoming = asyncio.Queue()
    incoming.put_nowait({'type': 'websocket.connect'})
    sent, children, scope = [], [], []
    started, cleanup_started = asyncio.Event(), asyncio.Event()
    cleanup_release, cleanup_finished = asyncio.Event(), asyncio.Event()
    close_finished = asyncio.Event()
    real_create = asyncio.create_task

    def create(coroutine, *args, **kwargs):
        task = real_create(coroutine, *args, **kwargs)
        if coroutine.__qualname__.startswith('relay.<locals>.'):
            children.append(task)
            if len(children) == 3:
                started.set()
        return task

    async def receive():
        try:
            return await incoming.get()
        except asyncio.CancelledError:
            cleanup_started.set()
            await cleanup_release.wait()
            cleanup_finished.set()
            raise

    async def send(message):
        sent.append(message)
        if message['type'] == 'websocket.close' and close_blocks:
            try:
                await asyncio.Event().wait()
            finally:
                close_finished.set()

    websocket = WebSocket({'type': 'websocket', 'path': '/api/fabric/relay', 'query_string': b'',
                           'headers': [(b'authorization', token_headers(peer)['Authorization'].encode())]}, receive, send)

    async def run():
        with anyio.CancelScope() as owner:
            scope.append(owner)
            await relay(websocket)

    monkeypatch.setattr(asyncio, 'create_task', create)
    handler = real_create(run())
    try:
        await asyncio.wait_for(started.wait(), 2)
        scope[0].cancel()
        await asyncio.wait_for(cleanup_started.wait(), 2)
        assert not fabric.relay.connected(peer['peer_id'])
        assert not handler.done()
        cleanup_release.set()
        await asyncio.wait_for(handler, 7)
        assert cleanup_finished.is_set()
        assert all(child.done() for child in children)
        assert sent[-1]['type'] == 'websocket.close'
        assert not close_blocks or close_finished.is_set()
    finally:
        cleanup_release.set()
        if scope:
            scope[0].cancel()
        await asyncio.wait_for(handler, 2)


def test_relay_rejects_cross_group_target_master_key_and_query_credentials():
    alice = direct_enroll('alice')
    group = fabric.save_group(fabric.GroupInput(name='other'), 'admin')
    bob = direct_enroll('bob', [group['id']])
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/api/fabric/relay', headers=ADMIN):
                pass
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/api/fabric/relay?token=secret', headers=token_headers(alice)):
                pass
        with client.websocket_connect('/api/fabric/relay', headers=token_headers(alice)) as source:
            source.send_bytes(uuid.UUID(bob['peer_id']).bytes + b'opaque')
            with pytest.raises(WebSocketDisconnect) as failure:
                source.receive_bytes()
            assert failure.value.code == 1008


def test_relay_revoked_idle_device_is_closed_and_frames_are_bounded():
    alice = direct_enroll('alice')
    with TestClient(app) as client:
        with client.websocket_connect('/api/fabric/relay', headers=token_headers(alice)) as source:
            response = client.post('/api/fabric/peers/' + alice['peer_id'] + '/revoke', headers=ADMIN)
            assert response.status_code == 200
            with pytest.raises(WebSocketDisconnect):
                source.receive_bytes()
        assert client.get('/api/fabric/agent/config', headers=token_headers(alice)).status_code == 401
        bob = direct_enroll('bob')
        with client.websocket_connect('/api/fabric/relay', headers=token_headers(bob)) as source:
            source.send_bytes(b'x' * (fabric.MAX_FRAME + 1))
            with pytest.raises(WebSocketDisconnect):
                source.receive_bytes()


@pytest.mark.asyncio
async def test_relay_queue_and_rate_are_bounded(monkeypatch):
    alice, bob = direct_enroll('alice'), direct_enroll('bob')
    source, recipient = fabric.RelayConnection(alice['peer_id']), fabric.RelayConnection(bob['peer_id'])
    manager = fabric.Relay()
    manager.register(source)
    manager.register(recipient)
    frame = uuid.UUID(bob['peer_id']).bytes + b'opaque'
    for _ in range(fabric.RELAY_QUEUE):
        assert manager.forward(source, frame)
    with pytest.raises(HTTPException) as failure:
        manager.forward(source, frame)
    assert failure.value.status_code == 429 and recipient.queue.qsize() == fabric.RELAY_QUEUE
    monkeypatch.setattr(fabric.time, 'monotonic', lambda: 1)
    limit = fabric.RateLimit()
    assert all(limit.allow(100) for _ in range(fabric.RELAY_RATE * 2))
    assert not limit.allow(100)


def test_viewer_read_only_and_admin_enrollment_role_gate(monkeypatch):
    monkeypatch.setenv('R_LINK_AUTH_MODE', 'oidc')
    monkeypatch.setenv('R_LINK_OIDC_ISSUER', 'https://id.example/realm')
    monkeypatch.setenv('R_LINK_OIDC_CLIENT_ID', 'rlink')
    monkeypatch.setenv('R_LINK_OIDC_CLIENT_SECRET', 'test-client-secret')
    monkeypatch.setenv('R_LINK_PUBLIC_URL', 'https://fabric.example/r-link')
    viewer = identity.upsert_identity({'iss': 'https://id.example/realm', 'sub': 'viewer'})
    with identity.database() as db:
        db.execute("UPDATE users SET role='viewer' WHERE id=?", (viewer['id'],))
    session = identity.create_session(viewer, 'desktop')
    headers = {'Authorization': 'Bearer ' + session['token'], 'X-R-Link-Session-Context': session['id']}
    with TestClient(app) as client:
        assert client.get('/api/fabric/peers', headers=headers).status_code == 200
        assert client.get('/api/fabric/status', headers=headers).status_code == 200
        assert client.post('/api/fabric/enrollments', headers=headers, json={'name': 'unauthorized'}).status_code == 403


def test_api_enrollment_projects_real_managed_inventory_without_fake_vpn_online():
    with TestClient(app) as client:
        issued = client.post('/api/fabric/enrollments', headers=ADMIN, json={'name': 'projection'}).json()
        peer = client.post('/api/fabric/enrollment', json={'enrollment_token': issued['enrollment_token'],
                           'name': 'Native Windows', 'os': 'windows', 'public_key': public_key()}).json()
        inventory = client.get('/api/devices', headers=ADMIN).json()
        assert len(inventory) == 1
        device = inventory[0]
        assert device['source'] == 'fabric' and device['peer_id'] == peer['peer_id']
        assert device['host'] == peer['virtual_ip'] and device['platform'] == 'windows'
        assert device['provider_url'] == 'https://fabric.example/r-link#rlink-fabric'
        assert device['connection_status'] == 'unknown'
        assert client.post('/api/fabric/agent/heartbeat', headers=token_headers(peer),
                           json={'tunnel_ready': False, 'mode': 'transport-test'}).status_code == 200
        assert devices.read_device(device['id'])['connection_status'] == 'unknown'
        body = {'name': 'Renamed by owner', 'host': device['host'], 'platform': 'linux'}
        assert client.put('/api/devices/' + device['id'], headers=ADMIN, json=body).status_code == 200
        assert client.put('/api/devices/' + device['id'], headers=ADMIN,
                          json=dict(body, host='192.168.5.99')).status_code == 409
        assert client.patch('/api/fabric/peers/' + peer['peer_id'], headers=ADMIN,
                            json={'name': 'Renamed upstream'}).status_code == 200
        preserved = devices.read_device(device['id'])
        assert preserved['name'] == 'Renamed by owner' and preserved['platform'] == 'linux' and preserved['source'] == 'fabric'
        assert client.post('/api/fabric/peers/' + peer['peer_id'] + '/revoke', headers=ADMIN).status_code == 200
        assert devices.read_device(device['id'])['connection_status'] == 'revoked'


def test_fabric_inventory_online_requires_real_vpn_telemetry_and_expires():
    alice, bob = direct_enroll('alice'), direct_enroll('bob')
    fabric_inventory.project(alice['peer_id'])
    device = devices.list_devices()[0]
    fabric.heartbeat(alice['peer_id'], fabric.Heartbeat(tunnel_ready=True, mode='vpn',
                      peer_status=[fabric.PeerStatus(peer_id=bob['peer_id'], path='direct', last_handshake=int(time.time()))]))
    assert devices.read_device(device['id'])['connection_status'] == 'online'
    with fabric.database() as db:
        db.execute('UPDATE fabric_peers SET last_seen=0 WHERE id=?', (alice['peer_id'],))
    assert devices.read_device(device['id'])['connection_status'] == 'unknown'
    devices.delete_device(device['id'])
    assert fabric_inventory.project(alice['peer_id']) == {'projected': False, 'reason': 'inventory_exclusion'}
    assert devices.list_devices() == []
