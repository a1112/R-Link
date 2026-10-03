"""Contract tests for reusing the existing R-File services."""
import json
import asyncio
import os
from pathlib import Path
import threading
from datetime import datetime

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from core.rfile import RFile


def test_rfile_status_requires_rlink_service_key(monkeypatch):
    monkeypatch.setenv('R_LINK_API_TOKEN', 'operator-key')
    with TestClient(app) as client:
        assert client.get('/api/rfile/status').status_code == 401


def test_rfile_status_reports_automatic_service_addresses_without_credentials(monkeypatch):
    monkeypatch.setenv('R_LINK_API_TOKEN', 'operator-key')
    monkeypatch.setenv('R_LINK_RFILE_INTERVAL', '0')
    with TestClient(app) as client:
        response = client.get('/api/rfile/status', headers={'Authorization': 'Bearer operator-key'})
        assert response.status_code == 200
        status = response.json()
        assert status['watch']['url'] == 'http://127.0.0.1:18080'
        assert status['network']['url'] == 'http://127.0.0.1:18100'
        assert status['files']['enabled'] is False
        assert status['devices'] == []
        assert 'token' not in json.dumps(status).lower()


def entry(path, kind='file', **extra):
    return {'name': path.replace('\\', '/').rsplit('/', 1)[-1], 'path': path,
            'kind': kind, 'size': 5 if kind == 'file' else None, 'mtime': '2026-10-03T00:00:00Z',
            'readonly': False, **extra}


class ExistingServices:
    """An HTTP transport implementing the actual watch/bridge wire contract."""
    def __init__(self):
        self.requests = []
        self.list_entries = [entry('/share/docs', 'folder'), entry('/share/actual.txt')]
        self.stats = {'/': entry('/', 'folder'), '/share': entry('/share', 'folder'),
                      '/share/docs': entry('/share/docs', 'folder'), '/share/actual.txt': entry('/share/actual.txt')}
        self.download = b'hello'

    def __call__(self, request):
        self.requests.append(request)
        path = request.url.path
        if path.endswith('/api/v1/bridge/health'):
            return httpx.Response(200, json={'service': 'rfile-bridge', 'status': 'ok', 'activeSessions': 2})
        if path.endswith('/api/v1/health'):
            return httpx.Response(200, json={'service': 'rfile-watch', 'status': 'ok'})
        if path.endswith('/api/v1/bridge/register'):
            return httpx.Response(200, json={'deviceId': json.loads(request.content)['deviceId'], 'accessToken': 'upstream-private'})
        if path.endswith('/api/v1/bridge/heartbeat') or path.endswith('/api/v1/bridge/unregister'):
            return httpx.Response(204)
        if path.endswith('/api/v1/bridge/devices'):
            return httpx.Response(200, json=[{'deviceId': 'nas', 'deviceName': 'DS918+', 'platform': 'linux',
                'presence': 'online', 'connectivity': 'relay', 'trustState': 'trusted', 'accessToken': 'secret-peer'}])
        if path.endswith('/api/v1/stat'):
            item = self.stats.get(request.url.params['path'])
            return httpx.Response(200, json=item) if item else httpx.Response(404)
        if path.endswith('/api/v1/list'):
            return httpx.Response(200, json={'path': request.url.params['path'], 'entries': self.list_entries})
        if path.endswith('/api/v1/download'):
            return httpx.Response(200, content=self.download)
        if path.endswith('/api/v1/upload'):
            return httpx.Response(200, json=entry('/share/upload.txt'))
        return httpx.Response(404)


def configured(monkeypatch, handler, **env):
    monkeypatch.setenv('R_LINK_RFILE_INTERVAL', '0')
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return RFile(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_reuses_environment_conventions_with_explicit_overrides_and_basepaths(monkeypatch):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, RFILE_SERVICE_URL='http://existing.test/watch',
                         RFILE_BRIDGE_URL='https://existing.test/r-file', R_LINK_RFILE_URL='http://override.test/root')
    await service.refresh()
    assert service.status()['watch']['url'] == 'http://override.test/root'
    assert service.status()['network']['url'] == 'https://existing.test/r-file'
    assert any(request.url.path == '/r-file/api/v1/bridge/register' for request in upstream.requests)
    await service.close()


@pytest.mark.asyncio
async def test_completed_downloads_keep_a_bounded_reservation_until_response_file_closes(monkeypatch):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    files = [await service.download('actual.txt') for _ in range(4)]
    try:
        with pytest.raises(HTTPException) as busy:
            await service.download('actual.txt')
        assert busy.value.status_code == 429
        files[0][0].close()
        files[0][0].close()
        file, _, _ = await service.download('actual.txt')
        file.close()
    finally:
        for file, _, _ in files:
            file.close()
        await service.close()


@pytest.mark.asyncio
async def test_shutdown_closes_download_files_still_owned_by_response(monkeypatch):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    file, _, _ = await service.download('actual.txt')
    await service.close()
    assert file.closed
    file.close()


@pytest.mark.asyncio
async def test_metadata_limit_prevents_over_limit_buffer_allocation(monkeypatch):
    from core import rfile
    limit = 32
    allocations = []
    class ObservedBuffer(bytearray):
        def extend(self, value):
            allocations.append(len(self) + len(value))
            super().extend(value)
    monkeypatch.setattr(rfile, 'MAX_JSON_BYTES', limit)
    monkeypatch.setattr(rfile, 'bytearray', ObservedBuffer, raising=False)
    service = configured(monkeypatch, lambda request: httpx.Response(200, content=b'x' * 1000))
    with pytest.raises(HTTPException) as invalid:
        await service.request('GET', service.watch_url, '/api/v1/health')
    assert invalid.value.status_code == 502
    assert all(size <= limit for size in allocations)
    await service.close()


@pytest.mark.asyncio
async def test_registers_own_durable_identity_heartbeats_and_never_discloses_tokens(monkeypatch, tmp_path):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream)
    await service.refresh()
    registration = next(request for request in upstream.requests if request.url.path.endswith('/register'))
    data = json.loads(registration.content)
    assert registration.headers['x-rfile-device-id'] == data['deviceId']
    assert len(registration.headers['x-rfile-device-token']) >= 32
    assert data['accessPolicy']['canInitiateRemoteSessions'] is True
    assert data['accessPolicy']['canAcceptRemoteSessions'] is False
    assert data['accessToken'] is None
    assert service.status()['network']['state'] == 'online'
    assert service.status()['devices'][0]['deviceId'] == 'nas'
    assert 'accessToken' not in json.dumps(service.status())
    await service.refresh()
    assert len([r for r in upstream.requests if r.url.path.endswith('/register')]) == 1
    assert len([r for r in upstream.requests if r.url.path.endswith('/heartbeat')]) == 1
    identity = Path(os.environ['R_LINK_DATA_DIR']) / 'rfile' / 'controller.json'
    assert identity.is_file()
    if os.name != 'nt':
        assert identity.stat().st_mode & 0o777 == 0o600
        assert identity.parent.stat().st_mode & 0o777 == 0o700
    await service.close()
    cleanup = [r for r in upstream.requests if r.url.path.endswith('/unregister')]
    assert len(cleanup) == 1
    assert json.loads(cleanup[0].content)['deviceId'] == data['deviceId']
    resumed = configured(monkeypatch, upstream)
    await resumed.refresh()
    again = [r for r in upstream.requests if r.url.path.endswith('/register')][-1]
    assert json.loads(again.content)['deviceId'] == data['deviceId']
    assert again.headers['x-rfile-device-token'] == registration.headers['x-rfile-device-token']
    await resumed.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['wrong-service', 'redirect', 'offline'])
async def test_health_identity_redirect_and_offline_errors_are_sanitized(monkeypatch, mode):
    seen = []
    def handler(request):
        seen.append(request)
        if mode == 'offline':
            raise httpx.ConnectError('secret-credential http://private/', request=request)
        if mode == 'redirect':
            return httpx.Response(302, headers={'Location': 'https://untrusted.test/stolen'})
        return httpx.Response(200, json={'service': 'unrelated', 'status': 'ok', 'token': 'secret-credential'})
    service = configured(monkeypatch, handler, R_LINK_RFILE_SESSION_TOKEN='secret-credential', R_LINK_RFILE_ROOT='/share')
    await service.refresh()
    status = service.status()
    assert status['watch']['state'] in {'offline', 'error'}
    assert status['network']['state'] in {'offline', 'error'}
    assert status['devices'] == []
    assert 'secret-credential' not in json.dumps(status)
    assert all(request.url.host == '127.0.0.1' for request in seen)
    assert all('x-rfile-session-token' not in request.headers for request in seen)
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('url', ['http://user:secret@host', 'ftp://host', 'https://host/?token=secret', 'https://host/#secret'])
async def test_invalid_configuration_is_safe_and_does_not_connect(monkeypatch, url):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_URL=url)
    await service.refresh()
    assert service.status()['config_error']
    assert not upstream.requests
    assert 'secret' not in json.dumps(service.status())
    await service.close()


@pytest.mark.asyncio
async def test_file_operations_require_an_explicit_credential_and_single_root(monkeypatch):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_ROOT='/share')
    with pytest.raises(HTTPException) as denied:
        await service.list_directory('')
    assert denied.value.status_code == 409
    assert not upstream.requests
    await service.close()
    monkeypatch.delenv('R_LINK_RFILE_ROOT')
    service = configured(monkeypatch, upstream, RFILE_SERVICE_ACCESS_TOKEN='secret', RFILE_ALLOWED_ROOTS='/share;/other')
    assert service.status()['files']['enabled'] is False
    await service.close()


@pytest.mark.asyncio
async def test_listing_uses_scoped_session_header_and_filters_links_and_outside_entries(monkeypatch):
    upstream = ExistingServices()
    upstream.list_entries += [entry('/outside/secret'), entry('/share/link', 'symlink'),
                             entry('/share/alias', isAlias=True), entry('/share/linked', linkTargetPath='/outside'),
                             entry('/share/sub/deep.txt'), entry('/share/mismatch', name='other')]
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='scoped-secret',
                         RFILE_SERVICE_ACCESS_TOKEN='admin-secret', R_LINK_RFILE_ROOT='/share')
    result = await service.list_directory('')
    assert [item['name'] for item in result['entries']] == ['docs', 'actual.txt']
    assert result['entries'][0]['kind'] == 'directory'
    assert result['skipped'] == 6
    assert result['max_file_bytes'] == 64 * 1024 * 1024
    operations = [r for r in upstream.requests if not r.url.path.endswith('/health')]
    assert all(r.headers.get('x-rfile-session-token') == 'scoped-secret' for r in operations)
    assert all('x-rfile-session-token' not in r.headers for r in upstream.requests if r.url.path.endswith('/health'))
    assert all('x-rfile-service-token' not in r.headers for r in upstream.requests)
    assert '/share' not in json.dumps(result)
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['../escape', '/share', 'sub/../escape', 'sub\\escape', 'C:/escape', 'a//b', '.', 'a\x00b'])
async def test_untrusted_relative_paths_are_rejected_before_network_access(monkeypatch, path):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with pytest.raises(HTTPException) as invalid:
        await service.list_directory(path)
    assert invalid.value.status_code == 400
    assert not upstream.requests
    await service.close()


@pytest.mark.asyncio
async def test_symlink_ancestor_and_wrong_snapshot_paths_are_rejected(monkeypatch):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    upstream.stats['/share'] = entry('/share', 'folder', symlinkTarget='/other')
    with pytest.raises(HTTPException) as invalid:
        await service.list_directory('docs')
    assert invalid.value.status_code == 403
    assert not any(r.url.path.endswith('/list') for r in upstream.requests)
    await service.close()


@pytest.mark.asyncio
async def test_upload_preserves_actual_multipart_protocol_and_rejects_overwrite(monkeypatch, tmp_path):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with (tmp_path / 'bytes').open('w+b') as file:
        file.write(b'hello'); file.seek(0)
        result = await service.upload('', 'upload.txt', file, 5)
    assert result['name'] == 'upload.txt'
    upload = next(r for r in upstream.requests if r.url.path.endswith('/upload'))
    body = upload.content
    assert body.index(b'name="path"') < body.index(b'name="file"')
    assert b'/share' in body and b'name="conflictPolicy"' in body and b'reject' in body
    assert b'filename="upload.txt"' in body and b'hello' in body
    await service.close()


@pytest.mark.asyncio
async def test_upstream_permission_and_conflict_errors_do_not_expose_response_body(monkeypatch, tmp_path):
    upstream = ExistingServices()
    def handler(request):
        if request.url.path.endswith('/upload'):
            return httpx.Response(409, json={'error': 'secret-token /private/path'})
        return upstream(request)
    service = configured(monkeypatch, handler, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with (tmp_path / 'bytes').open('w+b') as file:
        with pytest.raises(HTTPException) as conflict:
            await service.upload('', 'upload.txt', file, 0)
    assert conflict.value.status_code == 409
    assert 'secret-token' not in conflict.value.detail
    await service.close()


@pytest.mark.asyncio
async def test_download_real_bytes_and_transfer_limit(monkeypatch):
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    file, name, size = await service.download('actual.txt')
    try:
        assert file.read() == b'hello'
        assert name == 'actual.txt' and size == 5
    finally:
        file.close()
    upstream.stats['/share/actual.txt']['size'] = 64 * 1024 * 1024 + 1
    with pytest.raises(HTTPException) as large:
        await service.download('actual.txt')
    assert large.value.status_code == 413
    await service.close()


@pytest.mark.asyncio
async def test_shutdown_cancels_pending_discovery_and_closes_client(monkeypatch):
    entered = asyncio.Event()
    async def handler(request):
        entered.set()
        await asyncio.Event().wait()
    service = configured(monkeypatch, handler, R_LINK_RFILE_INTERVAL='30')
    await service.start()
    await asyncio.wait_for(entered.wait(), 1)
    await asyncio.wait_for(service.close(), 1)
    assert service.client.is_closed


@pytest.mark.asyncio
async def test_windows_remote_root_and_reserved_names(monkeypatch):
    upstream = ExistingServices()
    upstream.stats = {'C:\\Shared': entry('C:\\Shared', 'folder')}
    upstream.list_entries = [entry('C:\\Shared\\actual.txt'), entry('C:\\Outside\\secret'),
                             entry('C:\\Shared\\CON.txt')]
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='C:\\Shared')
    result = await service.list_directory('')
    assert [item['path'] for item in result['entries']] == ['actual.txt']
    assert result['skipped'] == 2
    with pytest.raises(HTTPException) as invalid:
        await service.list_directory('AUX')
    assert invalid.value.status_code == 400
    await service.close()


@pytest.mark.asyncio
async def test_close_unregisters_own_identity_after_peer_listing_fails(monkeypatch):
    upstream = ExistingServices()
    def handler(request):
        if request.url.path.endswith('/devices'):
            return httpx.Response(500, json={'error': 'secret'})
        return upstream(request)
    service = configured(monkeypatch, handler)
    await service.refresh()
    assert service.status()['devices'] == []
    await service.close()
    assert any(r.url.path.endswith('/unregister') for r in upstream.requests)


@pytest.mark.asyncio
async def test_background_refresh_survives_concurrent_operator_refresh(monkeypatch):
    service = configured(monkeypatch, ExistingServices(), R_LINK_RFILE_INTERVAL='1')
    await service.lock.acquire()
    await service.start()
    await asyncio.sleep(0.02)
    service.lock.release()
    await asyncio.sleep(1.05)
    assert not service.worker.done()
    assert service.status()['network']['state'] == 'online'
    await service.close()


@pytest.mark.asyncio
async def test_streamed_download_size_is_checked_even_when_metadata_understates_it(monkeypatch):
    from core import rfile
    monkeypatch.setattr(rfile, 'MAX_FILE_BYTES', 4)
    upstream = ExistingServices()
    upstream.stats['/share/actual.txt']['size'] = 1
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with pytest.raises(HTTPException) as large:
        await service.download('actual.txt')
    assert large.value.status_code == 413
    await service.close()


@pytest.mark.asyncio
async def test_api_transfers_bytes_and_rejects_untrusted_paths(monkeypatch):
    upstream = ExistingServices()
    monkeypatch.setenv('R_LINK_API_TOKEN', 'operator-key')
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with TestClient(app) as client:
        original = app.state.rfile
        app.state.rfile = service
        headers = {'Authorization': 'Bearer operator-key'}
        listing = client.get('/api/rfile/files', headers=headers)
        assert listing.status_code == 200
        assert listing.json()['entries'][0]['path'] == 'docs'
        response = client.put('/api/rfile/upload?name=upload.txt', headers=headers, content=b'hello')
        assert response.status_code == 201
        assert client.get('/api/rfile/download?path=actual.txt', headers=headers).content == b'hello'
        assert client.get('/api/rfile/files?path=../escape', headers=headers).status_code == 400
        assert client.put('/api/rfile/upload?name=../escape', headers=headers, content=b'hello').status_code == 400
        assert client.get('/api/rfile/files').status_code == 401
        app.state.rfile = original
    await service.close()


@pytest.mark.asyncio
async def test_wrong_snapshot_and_parent_stat_paths_are_not_trusted(monkeypatch):
    upstream = ExistingServices()
    def handler(request):
        if request.url.path.endswith('/list'):
            return httpx.Response(200, json={'path': '/outside', 'entries': []})
        return upstream(request)
    service = configured(monkeypatch, handler, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with pytest.raises(HTTPException) as invalid:
        await service.list_directory('')
    assert invalid.value.status_code == 403
    await service.close()
    upstream.stats['/share'] = entry('/outside', 'folder')
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with pytest.raises(HTTPException) as invalid:
        await service.list_directory('docs')
    assert invalid.value.status_code == 403
    await service.close()


@pytest.mark.asyncio
async def test_readonly_and_session_permission_cannot_be_bypassed(monkeypatch, tmp_path):
    upstream = ExistingServices()
    upstream.stats['/share']['readonly'] = True
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with (tmp_path / 'bytes').open('w+b') as file:
        with pytest.raises(HTTPException) as denied:
            await service.upload('', 'upload.txt', file, 0)
    assert denied.value.status_code == 403
    assert not any(r.url.path.endswith('/upload') for r in upstream.requests)
    await service.close()
    def forbidden(request):
        if request.url.path.endswith('/stat'):
            return httpx.Response(403, json={'error': 'secret-session /private'})
        return upstream(request)
    service = configured(monkeypatch, forbidden, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    with pytest.raises(HTTPException) as denied:
        await service.list_directory('')
    assert denied.value.status_code == 403 and 'secret-session' not in denied.value.detail
    await service.close()


@pytest.mark.asyncio
async def test_failed_and_cancelled_downloads_close_upstream_and_release_slot(monkeypatch):
    upstream = ExistingServices()
    entered = asyncio.Event()
    closed = asyncio.Event()
    class PendingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b'hello'
        async def aclose(self):
            closed.set()
    def handler(request):
        if request.url.path.endswith('/download'):
            return httpx.Response(200, stream=PendingStream())
        return upstream(request)
    service = configured(monkeypatch, handler, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    task = asyncio.create_task(service.download('actual.txt'))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()
    assert service.transfers._value == 4
    assert not service.downloads
    await service.close()


@pytest.mark.asyncio
async def test_identity_write_is_drained_before_cancelled_refresh_completes(monkeypatch):
    from core import rfile
    upstream = ExistingServices()
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    real = rfile.controller_identity
    def delayed(directory):
        entered.set()
        release.wait(2)
        data = real(directory)
        finished.set()
        return data
    monkeypatch.setattr(rfile, 'controller_identity', delayed)
    service = configured(monkeypatch, upstream)
    task = asyncio.create_task(service.refresh())
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
    finally:
        release.set()
        await service.close()


@pytest.mark.asyncio
async def test_duplicate_and_oversize_peer_identities_are_rejected(monkeypatch):
    upstream = ExistingServices()
    def handler(request):
        if request.url.path.endswith('/devices'):
            return httpx.Response(200, json=[{'deviceId': 'x' * 241}, {'deviceId': 'same'}, {'deviceId': 'same'}])
        return upstream(request)
    service = configured(monkeypatch, handler)
    await service.refresh()
    assert service.status()['network']['state'] == 'offline'
    assert service.status()['devices'] == []
    await service.close()


@pytest.mark.asyncio
async def test_upload_stream_enforces_limit_before_writing_oversize_chunk(monkeypatch):
    from core import rfile
    monkeypatch.setattr(rfile, 'MAX_FILE_BYTES', 4)
    upstream = ExistingServices()
    service = configured(monkeypatch, upstream, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    async def chunks():
        yield b'123'
        yield b'45'
    with pytest.raises(HTTPException) as large:
        await service.upload_stream('', 'upload.txt', chunks())
    assert large.value.status_code == 413
    assert not any(r.url.path.endswith('/upload') for r in upstream.requests)
    assert service.transfers._value == 4
    await service.close()


@pytest.mark.asyncio
async def test_successful_and_failed_checks_record_utc_observation_time(monkeypatch):
    service = configured(monkeypatch, ExistingServices())
    assert service.status()['watch'].get('checked_at') is None
    await service.refresh()
    for name in ('watch', 'network'):
        observed = service.status()[name].get('checked_at')
        assert observed is not None
        assert datetime.fromisoformat(observed).utcoffset().total_seconds() == 0
    await service.close()
    service = configured(monkeypatch, lambda request: httpx.Response(503))
    await service.refresh()
    for name in ('watch', 'network'):
        assert service.status()[name]['state'] == 'offline'
        assert datetime.fromisoformat(service.status()[name]['checked_at']).utcoffset().total_seconds() == 0
    await service.close()


@pytest.mark.asyncio
async def test_invalid_persisted_identity_is_sanitized_without_killing_discovery(monkeypatch):
    service = configured(monkeypatch, ExistingServices())
    service.identity_dir.mkdir(parents=True)
    (service.identity_dir / 'controller.json').write_text('["secret"]', encoding='utf-8')
    await service.refresh()
    assert service.status()['network']['state'] == 'offline'
    assert 'secret' not in json.dumps(service.status())
    await service.close()


@pytest.mark.asyncio
async def test_refresh_deadline_clears_previous_network_observation(monkeypatch):
    from core import rfile
    upstream = ExistingServices()
    stalled = False
    async def handler(request):
        if stalled and request.url.path.endswith('/bridge/health'):
            await asyncio.Event().wait()
        return upstream(request)
    service = configured(monkeypatch, handler)
    await service.refresh()
    previous = service.status()['network']['checked_at']
    real_timeout = asyncio.timeout
    monkeypatch.setattr(rfile.asyncio, 'timeout', lambda seconds: real_timeout(0.02 if seconds == 15 else seconds))
    stalled = True
    with pytest.raises(HTTPException) as unavailable:
        await service.refresh()
    assert unavailable.value.status_code == 503
    assert service.status()['network']['state'] == 'offline'
    assert service.status()['network']['checked_at'] != previous
    assert service.status()['devices'] == []
    await service.close()


@pytest.mark.asyncio
async def test_disconnect_before_first_response_chunk_closes_download_lease(monkeypatch):
    from api.rfile import download
    from starlette.requests import Request, ClientDisconnect
    service = configured(monkeypatch, ExistingServices(), R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    original = getattr(app.state, 'rfile', None)
    app.state.rfile = service
    scope = {'type': 'http', 'method': 'GET', 'path': '/api/rfile/download', 'headers': [],
             'query_string': b'', 'app': app, 'asgi': {'spec_version': '2.4'}}
    async def receive():
        return {'type': 'http.disconnect'}
    async def send(message):
        raise BrokenPipeError()
    async def waiting_receive():
        await asyncio.Event().wait()
    try:
        response = await download(Request(scope, waiting_receive), 'actual.txt')
        with pytest.raises(ClientDisconnect):
            await response(scope, receive, send)
        assert not service.downloads
        assert service.transfers._value == 4
    finally:
        app.state.rfile = original
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['GET', 'PUT'])
async def test_browser_disconnect_cancels_pending_upstream_transfer_via_asgi_receive(monkeypatch, method):
    upstream = ExistingServices()
    entered = asyncio.Event()
    disconnected = asyncio.Event()
    upstream_closed = asyncio.Event()
    calls = []
    class PendingDownload(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b'hello'
        async def aclose(self):
            upstream_closed.set()
    async def handler(request):
        if request.url.path.endswith('/download'):
            return httpx.Response(200, stream=PendingDownload())
        if request.url.path.endswith('/upload'):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                upstream_closed.set()
        return upstream(request)
    service = configured(monkeypatch, handler, R_LINK_RFILE_SESSION_TOKEN='secret', R_LINK_RFILE_ROOT='/share')
    monkeypatch.setenv('R_LINK_API_TOKEN', 'operator-key')
    original = getattr(app.state, 'rfile', None)
    app.state.rfile = service
    endpoint = 'download?path=actual.txt' if method == 'GET' else 'upload?name=upload.txt'
    path, query = endpoint.split('?')
    scope = {'type': 'http', 'method': method, 'path': '/api/rfile/' + path,
             'headers': [(b'authorization', b'Bearer operator-key')], 'query_string': query.encode(),
             'scheme': 'http', 'server': ('127.0.0.1', 8210), 'client': ('127.0.0.1', 10001),
             'asgi': {'version': '3.0', 'spec_version': '2.4'}}
    first = True
    async def receive():
        nonlocal first
        calls.append('receive')
        if first:
            first = False
            return {'type': 'http.request', 'body': b'hello' if method == 'PUT' else b'', 'more_body': False}
        await disconnected.wait()
        return {'type': 'http.disconnect'}
    sent = []
    async def send(message):
        sent.append(message)
    task = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        disconnected.set()
        done, _ = await asyncio.wait({task}, timeout=0.1)
        assert task in done, 'ASGI disconnect must stop the pending upstream transfer immediately'
        await task
        assert calls
        assert upstream_closed.is_set()
        assert service.transfers._value == 4
        assert not service.downloads
        assert next(row['status'] for row in sent if row['type'] == 'http.response.start') == 499
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        app.state.rfile = original
        await service.close()


@pytest.mark.asyncio
async def test_bridge_active_session_count_is_observed_and_cleared_on_failure(monkeypatch):
    upstream = ExistingServices()
    failed = False
    def handler(request):
        if failed and request.url.path.endswith('/bridge/health'):
            return httpx.Response(503)
        return upstream(request)
    service = configured(monkeypatch, handler)
    assert service.status()['network'].get('active_sessions') is None
    await service.refresh()
    assert service.status()['network'].get('active_sessions') == 2
    failed = True
    await service.refresh()
    assert service.status()['network']['state'] == 'offline'
    assert service.status()['network'].get('active_sessions') is None
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('count', [-1, True, '2', None, 2 ** 53])
async def test_invalid_bridge_session_counts_are_not_shown_as_verified_state(monkeypatch, count):
    upstream = ExistingServices()
    def handler(request):
        if request.url.path.endswith('/bridge/health'):
            return httpx.Response(200, json={'service': 'rfile-bridge', 'status': 'ok', 'activeSessions': count})
        return upstream(request)
    service = configured(monkeypatch, handler)
    await service.refresh()
    assert service.status()['network']['state'] == 'offline'
    assert service.status()['network'].get('active_sessions') is None
    assert not any(r.url.path.endswith('/register') for r in upstream.requests)
    await service.close()
