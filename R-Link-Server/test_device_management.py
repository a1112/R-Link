"""Unified inventory contracts, isolated from any production control plane."""
import asyncio
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from core import devices, mesh
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(tmp_path / 'devices.sqlite'))
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 5555)) as value:
        yield value


def test_legacy_database_migrates_without_changing_identity_or_observation(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.sqlite'
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(path))
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE devices (id TEXT PRIMARY KEY,name TEXT NOT NULL,host TEXT NOT NULL,port INTEGER NOT NULL,username TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'unchecked',checked_at TEXT,latency_ms REAL,UNIQUE(host,port))")
        db.execute("INSERT INTO devices VALUES ('original-id','NAS','nas.local',2222,'admin',7,'reachable','2026-01-01',3.2)")
    row = devices.list_devices()[0]
    assert (row['id'], row['host'], row['port'], row['username'], row['revision'], row['status'], row['checked_at'], row['latency_ms']) == ('original-id', 'nas.local', 2222, 'admin', 7, 'reachable', '2026-01-01', 3.2)
    assert row['source'] == 'manual'
    assert row['access_mode'] == 'ssh'
    assert row['connection_status'] == 'unknown'
    assert row['tags'] == [] and row['peer_id'] is None


def test_metadata_normalizes_and_legacy_put_preserves_metadata(client):
    response = client.post('/api/devices', json={'name': 'NAS', 'host': 'nas.local', 'device_type': 'nas', 'platform': 'linux', 'tags': [' home ', 'home', ' media '], 'notes': ' rack ', 'access_mode': 'web', 'web_scheme': 'https'})
    assert response.status_code == 201
    row = response.json()
    assert row['tags'] == ['home', 'media']
    assert row['notes'] == 'rack'
    updated = client.put('/api/devices/' + row['id'], json={'name': 'renamed', 'host': 'nas.local'}).json()
    assert updated['device_type'] == 'nas' and updated['platform'] == 'linux'
    assert updated['tags'] == ['home', 'media'] and updated['access_mode'] == 'web'
    assert client.get('/api/devices/' + row['id']).json() == updated


@pytest.mark.parametrize('metadata', [{'tags': ['']}, {'tags': ['a' * 33]}, {'tags': [str(n) for n in range(17)]}, {'notes': 'a' * 501}, {'device_type': 'alien'}, {'platform': 'plan9'}, {'access_mode': 'telnet'}, {'gateway_id': 'missing'}])
def test_invalid_metadata_is_rejected_without_writing(client, metadata):
    assert client.post('/api/devices', json={'name': 'bad', 'host': 'bad.local', **metadata}).status_code in (409, 422)
    assert devices.list_devices() == []


def test_portable_v2_export_and_import_excludes_identity_and_gateway(client):
    row = client.post('/api/devices', json={'name': 'NAS', 'host': 'nas.local', 'device_type': 'nas', 'tags': ['home'], 'access_mode': 'web'}).json()
    v1 = client.get('/api/devices/export').json()
    assert set(v1['devices'][0]) == {'name', 'host', 'port', 'username'}
    v2 = client.get('/api/devices/export?version=2').json()
    assert v2['version'] == 2
    assert v2['devices'][0]['tags'] == ['home']
    assert not {'id', 'peer_id', 'source', 'connection_status', 'gateway_id', 'checked_at'} & v2['devices'][0].keys()
    client.delete('/api/devices/' + row['id'])
    assert client.post('/api/devices/import', json=v2).json() == {'added': 1, 'skipped': 0}
    assert devices.list_devices()[0]['device_type'] == 'nas'


@pytest.mark.parametrize('field', ['password', 'token', 'source', 'peer_id', 'provider', 'gateway_id', 'connection_status'])
def test_import_rejects_credentials_and_external_identity(client, field):
    response = client.post('/api/devices/import', json={'version': 2, 'devices': [{'name': 'good', 'host': 'good.local'}, {'name': 'bad', 'host': 'bad.local', field: 'secret'}]})
    assert response.status_code == 422
    assert devices.list_devices() == []


def peer(peer_id='peer1', ip='100.100.1.1', **changes):
    return {'id': peer_id, 'name': 'upstream laptop', 'ip': ip, 'connected': True, 'os': 'linux', 'last_seen': '2026-10-02T10:00:00Z', 'groups': [{'id': 'group1', 'name': 'home'}], 'ssh_enabled': True, 'user_id': 'private-user', **changes}


def configure(monkeypatch, handler):
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test/')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'private-pat')
    monkeypatch.setattr(mesh.netbird, 'transport', httpx.MockTransport(handler))


def test_sync_stable_identity_preserves_local_metadata_and_clears_changed_ip_probe(client, monkeypatch):
    upstream = [peer()]
    configure(monkeypatch, lambda request: httpx.Response(200, json=upstream))
    result = client.post('/api/devices/sync')
    assert result.status_code == 200
    assert result.json()['added'] == 1
    row = client.get('/api/devices').json()[0]
    assert row['source'] == 'netbird' and row['peer_id'] == 'peer1'
    assert row['connection_status'] == 'online' and row['platform'] == 'linux'
    assert row['access_mode'] == 'none'
    assert row['mesh_groups'] == [{'id': 'group1', 'name': 'home'}]
    assert not {'provider', 'user_id', 'ssh_enabled', 'name_override'} & row.keys()
    edited = client.put('/api/devices/' + row['id'], json={'name': 'my laptop', 'host': row['host'], 'port': 2222, 'username': 'admin', 'tags': ['home'], 'notes': 'keep', 'device_type': 'computer', 'access_mode': 'ssh'}).json()
    devices.record_probe(edited, True, 2.3)
    upstream[:] = [peer(ip='100.100.1.2', name='new upstream name', connected=False)]
    summary = client.post('/api/devices/sync').json()
    assert summary['updated'] == 1 and summary['added'] == 0
    changed = client.get('/api/devices/' + row['id']).json()
    assert changed['id'] == row['id'] and changed['name'] == 'my laptop'
    assert changed['host'] == '100.100.1.2' and changed['revision'] == edited['revision'] + 1
    assert changed['port'] == 2222 and changed['username'] == 'admin' and changed['notes'] == 'keep'
    assert changed['tags'] == ['home'] and changed['access_mode'] == 'ssh'
    assert changed['status'] == 'unchecked' and changed['checked_at'] is None
    assert changed['connection_status'] == 'offline'


def test_conflicting_manual_endpoint_requires_explicit_link_and_preserves_id(client, monkeypatch):
    manual = client.post('/api/devices', json={'name': 'local name', 'host': '100.100.1.1', 'tags': ['local'], 'access_mode': 'ssh'}).json()
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json=[peer()] if request.url.path == '/api/peers' else peer())
    configure(monkeypatch, handler)
    result = client.post('/api/devices/sync').json()
    assert result['added'] == 0 and result['conflicts'][0]['device_id'] == manual['id']
    assert client.get('/api/devices').json()[0]['source'] == 'manual'
    linked = client.post('/api/devices/' + manual['id'] + '/link', json={'peer_id': 'peer1'})
    assert linked.status_code == 200
    row = linked.json()
    assert row['id'] == manual['id'] and row['name'] == 'local name'
    assert row['tags'] == ['local'] and row['access_mode'] == 'ssh'
    assert row['source'] == 'netbird' and row['connection_status'] == 'online'
    assert ('GET', '/api/peers/peer1') in calls


def test_already_linked_peer_returns_409_without_merging_rows(client, monkeypatch):
    configure(monkeypatch, lambda request: httpx.Response(200, json=[peer()] if request.url.path == '/api/peers' else peer()))
    client.post('/api/devices/sync')
    manual = client.post('/api/devices', json={'name': 'other', 'host': 'other.local'}).json()
    assert client.post('/api/devices/' + manual['id'] + '/link', json={'peer_id': 'peer1'}).status_code == 409
    assert len(devices.list_devices()) == 2


def test_missing_failed_stale_and_switched_provider_states_are_truthful(client, monkeypatch):
    response = [peer()]
    configure(monkeypatch, lambda request: httpx.Response(200, json=response))
    client.post('/api/devices/sync')
    row = devices.list_devices()[0]
    response[:] = []
    assert client.post('/api/devices/sync').json()['missing'] == 1
    assert devices.read_device(row['id'])['connection_status'] == 'removed'
    response[:] = [peer()]
    client.post('/api/devices/sync')
    monkeypatch.setattr(mesh.netbird, 'transport', httpx.MockTransport(lambda request: httpx.Response(401, text='private-pat')))
    assert client.post('/api/devices/sync').status_code == 502
    assert devices.read_device(row['id'])['connection_status'] == 'unknown'
    status = client.get('/api/devices/management-status').json()
    assert status['last_error'] and 'private-pat' not in str(status)
    configure(monkeypatch, lambda request: httpx.Response(200, json=response))
    client.post('/api/devices/sync')
    with devices.database() as db:
        db.execute('UPDATE devices SET synced_at=?', ((datetime.now(timezone.utc) - timedelta(seconds=181)).isoformat(),))
    assert devices.read_device(row['id'])['connection_status'] == 'unknown'
    client.post('/api/devices/sync')
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://other.example.test')
    assert devices.read_device(row['id'])['connection_status'] == 'unknown'
    assert client.get('/api/devices/management-status').json()['last_synced_at'] is None


@pytest.mark.parametrize('invalid', [peer(ip='https://bad'), peer(connected='true'), peer(groups=[{'id': 'a', 'name': None}]), peer(last_seen='yesterday'), peer(id='../bad'), peer(name='')])
def test_malformed_sync_response_rolls_back_all_inventory_changes(client, monkeypatch, invalid):
    configure(monkeypatch, lambda request: httpx.Response(200, json=[peer('good'), invalid]))
    assert client.post('/api/devices/sync').status_code == 502
    assert devices.list_devices() == []


def test_sync_capacity_failure_rolls_back_all_new_peers(client, monkeypatch):
    with devices.database() as db:
        db.executemany('INSERT INTO devices(id,name,host,port,username) VALUES(?,?,?,?,?)', [(str(i), str(i), f'host{i}.local', 22, '') for i in range(255)])
    configure(monkeypatch, lambda request: httpx.Response(200, json=[peer('one'), peer('two', '100.100.1.2')]))
    assert client.post('/api/devices/sync').status_code == 409
    assert len(devices.list_devices()) == 255
    assert all(row['source'] == 'manual' for row in devices.list_devices())


def test_inventory_deletion_persists_exclusion_without_revoking_peer(client, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json=[peer()] if request.url.path == '/api/peers' else peer())
    configure(monkeypatch, handler)
    client.post('/api/devices/sync')
    row = devices.list_devices()[0]
    assert client.delete('/api/devices/' + row['id']).status_code == 204
    assert client.post('/api/devices/sync').json()['added'] == 0
    assert devices.list_devices() == [] and 'DELETE' not in calls
    manual = client.post('/api/devices', json={'name': 'manual', 'host': '100.100.1.1'}).json()
    assert client.post('/api/devices/' + manual['id'] + '/link', json={'peer_id': 'peer1'}).status_code == 200
    assert client.post('/api/devices/sync').json()['updated'] == 1


def test_revoke_changes_lifecycle_only_after_upstream_success_and_is_idempotent(client, monkeypatch):
    delete_status = [500]
    def handler(request):
        if request.method == 'DELETE':
            return httpx.Response(delete_status[0])
        return httpx.Response(200, json=[peer()])
    configure(monkeypatch, handler)
    client.post('/api/devices/sync')
    row = devices.list_devices()[0]
    assert client.post('/api/devices/' + row['id'] + '/revoke').status_code == 502
    assert devices.read_device(row['id'])['connection_status'] == 'online'
    delete_status[0] = 404
    result = client.post('/api/devices/' + row['id'] + '/revoke')
    assert result.status_code == 200 and result.json()['connection_status'] == 'revoked'
    assert client.post('/api/devices/' + row['id'] + '/revoke').status_code == 200
    assert client.post('/api/devices/sync').json()['added'] == 0
    assert devices.read_device(row['id'])['connection_status'] == 'revoked'
    manual = client.post('/api/devices', json={'name': 'manual', 'host': 'manual.local'}).json()
    assert client.post('/api/devices/' + manual['id'] + '/revoke').status_code == 409


def test_gateway_status_is_separate_and_deletion_detaches_children(client, monkeypatch):
    configure(monkeypatch, lambda request: httpx.Response(200, json=[peer()]))
    client.post('/api/devices/sync')
    gateway = devices.list_devices()[0]
    child = client.post('/api/devices', json={'name': 'IoT', 'host': '192.168.1.10', 'device_type': 'iot', 'gateway_id': gateway['id'], 'access_mode': 'web'}).json()
    assert child['source'] == 'gateway' and child['connection_status'] == 'unknown'
    assert child['gateway_status'] == 'online'
    assert client.put('/api/devices/' + gateway['id'], json={'name': 'recursive', 'host': gateway['host'], 'gateway_id': child['id']}).status_code == 409
    assert client.put('/api/devices/' + gateway['id'], json={'name': 'self', 'host': gateway['host'], 'gateway_id': gateway['id']}).status_code == 409
    assert client.post('/api/devices', json={'name': 'dangling', 'host': '192.168.1.11', 'gateway_id': child['id']}).status_code == 409
    client.delete('/api/devices/' + gateway['id'])
    detached = devices.read_device(child['id'])
    assert detached['gateway_id'] is None and detached['source'] == 'manual'
    assert detached['gateway_status'] is None


def test_management_status_onboarding_and_audit_never_expose_pat(client, monkeypatch):
    initial = client.get('/api/devices/management-status').json()
    assert initial == {'configured': False, 'syncing': False, 'interval_seconds': 0, 'stale_seconds': 180, 'last_synced_at': None, 'last_error': None}
    assert client.post('/api/devices/sync').status_code == 503
    configure(monkeypatch, lambda request: httpx.Response(200, json=[peer()]))
    onboarding = client.get('/api/devices/onboarding').json()
    assert onboarding['configured'] is True
    assert onboarding['management_url'] == 'https://mesh.example.test'
    assert {item['id'] for item in onboarding['platforms']} == {'windows', 'linux', 'macos', 'android', 'ios'}
    assert all(item['url'].startswith('https://docs.netbird.io/') for item in onboarding['platforms'])
    client.post('/api/devices/sync')
    assert client.get('/api/devices/management-status').json()['last_synced_at']
    row = devices.list_devices()[0]
    client.delete('/api/devices/' + row['id'])
    events = client.get('/api/audit').json()
    assert any(event['action'] == 'devices.sync' for event in events)
    assert any(event['action'] == 'devices.delete' for event in events)
    assert 'private-pat' not in str(events)


def test_manual_platform_override_survives_link_and_upstream_changes(client, monkeypatch):
    upstream = [peer()]
    configure(monkeypatch, lambda request: httpx.Response(200, json=upstream if request.url.path == '/api/peers' else upstream[0]))
    manual = client.post('/api/devices', json={'name': 'manual', 'host': '100.100.1.1', 'platform': 'windows'}).json()
    linked = client.post('/api/devices/' + manual['id'] + '/link', json={'peer_id': 'peer1'}).json()
    assert linked['platform'] == 'windows'
    upstream[0]['os'] = 'android'
    client.post('/api/devices/sync')
    assert devices.read_device(manual['id'])['platform'] == 'windows'


def test_imported_peer_platform_tracks_upstream_until_overridden(client, monkeypatch):
    upstream = [peer()]
    configure(monkeypatch, lambda request: httpx.Response(200, json=upstream))
    client.post('/api/devices/sync')
    row = devices.list_devices()[0]
    upstream[0]['os'] = 'darwin'
    client.post('/api/devices/sync')
    assert devices.read_device(row['id'])['platform'] == 'macos'


def test_linking_one_peer_does_not_restore_other_failed_observations(client, monkeypatch):
    upstream = [peer('one'), peer('two', '100.100.1.2')]
    configure(monkeypatch, lambda request: httpx.Response(200, json=upstream))
    client.post('/api/devices/sync')
    rows = devices.list_devices()
    monkeypatch.setattr(mesh.netbird, 'transport', httpx.MockTransport(lambda request: httpx.Response(500)))
    client.post('/api/devices/sync')
    assert all(row['connection_status'] == 'unknown' for row in devices.list_devices())
    configure(monkeypatch, lambda request: httpx.Response(200, json=upstream[0]))
    own = next(row for row in rows if row['peer_id'] == 'one')
    assert client.post('/api/devices/' + own['id'] + '/link', json={'peer_id': 'one'}).json()['connection_status'] == 'online'
    other = next(row for row in rows if row['peer_id'] == 'two')
    assert devices.read_device(other['id'])['connection_status'] == 'unknown'


def test_migration_failure_rolls_back_every_added_column(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.sqlite'
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(path))
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE devices(id TEXT PRIMARY KEY,name TEXT NOT NULL,host TEXT NOT NULL,port INTEGER NOT NULL,username TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'unchecked',checked_at TEXT,latency_ms REAL,UNIQUE(host,port))")
    monkeypatch.setitem(devices.COLUMNS, 'invalid_column', 'NOT VALID SQL )')
    with pytest.raises(sqlite3.OperationalError):
        devices.list_devices()
    with sqlite3.connect(path) as db:
        columns = [row[1] for row in db.execute('PRAGMA table_info(devices)')]
    assert 'device_type' not in columns and 'provider' not in columns


@pytest.mark.asyncio
async def test_background_sync_is_cancelled_before_service_lock_release(monkeypatch):
    from core.device_sync import DeviceSync
    from core.services import Services
    monkeypatch.setenv('R_LINK_DEVICE_SYNC_INTERVAL', '60')
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'isolated')
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    async def blocked(method, path):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    monkeypatch.setattr(mesh.netbird, 'request', blocked)
    services = Services()
    sync = DeviceSync(services.state)
    await services.start()
    await sync.start()
    await asyncio.wait_for(entered.wait(), 2)
    assert sync.status()['syncing'] is True
    await sync.close()
    assert cancelled.is_set() and sync.task is None and not sync.syncing
    assert services.owns_lock
    await services.close()


@pytest.mark.asyncio
async def test_manual_mode_never_contacts_netbird_at_startup(monkeypatch):
    from core.device_sync import DeviceSync
    called = []
    async def unexpected(*args):
        called.append(args)
        raise AssertionError('No startup request in manual mode')
    monkeypatch.setattr(mesh.netbird, 'request', unexpected)
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'isolated')
    sync = DeviceSync()
    await sync.start()
    await asyncio.sleep(0)
    assert sync.task is None and called == []
    await sync.close()


@pytest.mark.asyncio
async def test_sync_and_revoke_serialize_so_inflight_snapshot_cannot_resurrect(monkeypatch):
    from core.device_sync import DeviceSync
    from core.device_sync import apply_sync, validate_peers
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'isolated')
    apply_sync(validate_peers([peer()]), devices.current_provider())
    row = devices.list_devices()[0]
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []
    async def adapter(method, path):
        calls.append(method)
        if method == 'GET':
            entered.set()
            await release.wait()
            return [peer()]
        return None
    monkeypatch.setattr(mesh.netbird, 'request', adapter)
    sync = DeviceSync()
    syncing = asyncio.create_task(sync.sync())
    await asyncio.wait_for(entered.wait(), 2)
    revoking = asyncio.create_task(sync.revoke(row['id']))
    await asyncio.sleep(0)
    assert calls == ['GET'] and not revoking.done()
    release.set()
    await syncing
    await revoking
    assert devices.read_device(row['id'])['connection_status'] == 'revoked'
    assert calls == ['GET', 'DELETE']


@pytest.mark.asyncio
async def test_lifecycle_releases_services_when_device_worker_cleanup_errors(monkeypatch):
    import main
    from types import SimpleNamespace
    events = []
    class FakeServices:
        state = None
        async def start(self):
            events.append('acquire')
        async def close(self):
            events.append('release')
    class FakeSync:
        def __init__(self, state):
            pass
        async def start(self):
            events.append('sync.start')
        async def close(self):
            events.append('sync.close')
            raise RuntimeError('worker failed')
    monkeypatch.setattr(main, 'Services', FakeServices)
    monkeypatch.setattr(main, 'DeviceSync', FakeSync)
    with pytest.raises(RuntimeError, match='worker failed'):
        async with main.lifespan(SimpleNamespace(state=SimpleNamespace())):
            pass
    assert events == ['acquire', 'sync.start', 'sync.close', 'release']


@pytest.mark.asyncio
async def test_unexpected_sync_error_invalidates_old_mesh_observation(monkeypatch):
    from core.device_sync import DeviceSync, apply_sync, validate_peers
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'isolated')
    apply_sync(validate_peers([peer()]), devices.current_provider())
    row = devices.list_devices()[0]
    async def failed(*args):
        raise RuntimeError('private error detail')
    monkeypatch.setattr(mesh.netbird, 'request', failed)
    sync = DeviceSync()
    with pytest.raises(HTTPException) as error:
        await sync.sync()
    assert error.value.status_code == 502 and 'private' not in str(error.value.detail)
    assert devices.read_device(row['id'])['connection_status'] == 'unknown'
    assert sync.status()['last_error']


def test_changed_ip_conflict_invalidates_online_and_old_tcp_observations(client, monkeypatch):
    upstream = [peer()]
    configure(monkeypatch, lambda request: httpx.Response(200, json=upstream))
    client.post('/api/devices/sync')
    bound = devices.list_devices()[0]
    devices.record_probe(bound, True, 3.4)
    manual = client.post('/api/devices', json={'name': 'manual', 'host': '100.100.1.2'}).json()
    upstream[:] = [peer(ip='100.100.1.2')]
    result = client.post('/api/devices/sync').json()
    assert result['conflicts'][0]['device_id'] == manual['id']
    conflicted = devices.read_device(bound['id'])
    assert conflicted['connection_status'] == 'unknown'
    assert conflicted['status'] == 'unchecked' and conflicted['checked_at'] is None and conflicted['latency_ms'] is None
    assert conflicted['revision'] == bound['revision'] + 1
    assert conflicted['host'] == bound['host']
    assert devices.record_probe(bound, True, 1.0) == conflicted
    assert devices.read_device(manual['id']) == manual


@pytest.mark.asyncio
async def test_close_waits_for_cancelled_background_database_worker(monkeypatch):
    from core import device_sync as ds
    monkeypatch.setenv('R_LINK_DEVICE_SYNC_INTERVAL', '60')
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'isolated')
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = ds.apply_sync
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        try:
            return original(*args)
        finally:
            finished.set()
    async def adapter(*args):
        return [peer()]
    events = []
    class AuditState:
        def audit(self, action, resource):
            events.append((action, resource))
    monkeypatch.setattr(ds, 'apply_sync', blocked)
    monkeypatch.setattr(mesh.netbird, 'request', adapter)
    sync = ds.DeviceSync(AuditState())
    await sync.start()
    assert await asyncio.to_thread(entered.wait, 2)
    closing = asyncio.create_task(sync.close())
    try:
        await asyncio.sleep(0.05)
        assert not closing.done()
        assert sync.lock.locked() and sync.syncing and not finished.is_set()
    finally:
        release.set()
        await closing
    assert finished.is_set() and sync.task is None and not sync.syncing
    assert not sync.lock.locked() and len(devices.list_devices()) == 1
    assert ('devices.sync', 'inventory') in events


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['link', 'revoke', 'probe'])
async def test_cancelled_operation_waits_for_actual_database_work(monkeypatch, operation):
    from core import device_sync as ds
    from api import devices as api
    from types import SimpleNamespace
    monkeypatch.setenv('R_LINK_NETBIRD_URL', 'https://mesh.example.test')
    monkeypatch.setenv('R_LINK_NETBIRD_TOKEN', 'isolated')
    if operation == 'revoke':
        ds.apply_sync(ds.validate_peers([peer()]), devices.current_provider())
        row = devices.list_devices()[0]
    else:
        row = devices.save_device(devices.DeviceInput(name='manual', host='100.100.1.1'))
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    owner, name = (devices, 'record_probe') if operation == 'probe' else (ds, 'apply_link' if operation == 'link' else 'mark_revoked')
    original = getattr(owner, name)
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        try:
            return original(*args)
        finally:
            finished.set()
    async def adapter(method, path):
        return peer() if method == 'GET' else None
    async def refused(*args):
        raise OSError('isolated refusal')
    monkeypatch.setattr(owner, name, blocked)
    monkeypatch.setattr(mesh.netbird, 'request', adapter)
    sync = ds.DeviceSync()
    if operation == 'link':
        running = asyncio.create_task(sync.link(row['id'], 'peer1'))
    elif operation == 'revoke':
        running = asyncio.create_task(sync.revoke(row['id']))
    else:
        monkeypatch.setattr(api.asyncio, 'open_connection', refused)
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(device_sync=sync)))
        running = asyncio.create_task(api.probe_device(row['id'], request))
    assert await asyncio.to_thread(entered.wait, 2)
    running.cancel()
    closing = asyncio.create_task(sync.close())
    try:
        await asyncio.sleep(0.05)
        running.cancel()  # A second cancellation must not abandon the worker.
        await asyncio.sleep(0)
        assert not running.done() and not closing.done()
        assert sync.lock.locked() and not finished.is_set()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await running
        await closing
    assert finished.is_set() and not sync.lock.locked()
    updated = devices.read_device(row['id'])
    if operation == 'link':
        assert updated['source'] == 'netbird'
    elif operation == 'revoke':
        assert updated['connection_status'] == 'revoked'
    else:
        assert updated['status'] == 'unreachable'
