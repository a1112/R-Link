import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp
from aiohttp import web
import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.service_state import ServiceState
from core.services import Services
from core.managed_service import ManagedService, recover_processes
from core.downloads import DownloadInput, DownloadManager, PublicResolver
from core.tunnels import TunnelInput, TunnelManager, frp_config
from core.domains import DomainInput, DomainManager, DNSInput, caddy_config
from core import domains
from main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 12345)) as value:
        yield value


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/services'), ('GET', '/api/audit'), ('GET', '/api/downloads'),
    ('POST', '/api/downloads'), ('POST', '/api/downloads/missing/pause'), ('GET', '/api/downloads/missing/file'),
    ('DELETE', '/api/downloads/missing'), ('GET', '/api/tunnels'), ('POST', '/api/tunnels'),
    ('PUT', '/api/tunnels/missing'), ('DELETE', '/api/tunnels/missing'), ('POST', '/api/tunnels/missing/start'),
    ('GET', '/api/tunnels/missing/logs'), ('GET', '/api/domains'), ('POST', '/api/domains'),
    ('PUT', '/api/domains/missing'), ('DELETE', '/api/domains/missing'), ('GET', '/api/domains/service'),
    ('POST', '/api/domains/service/apply'), ('POST', '/api/domains/service/stop'), ('GET', '/api/domains/service/logs'),
    ('POST', '/api/domains/missing/check'), ('GET', '/api/domains/missing/dns'),
    ('POST', '/api/domains/missing/dns'), ('DELETE', '/api/domains/missing/dns/missing'),
])
def test_new_endpoints_require_auth(method, path):
    with TestClient(app) as remote:
        assert remote.request(method, path).status_code == 401


def test_inventory_validation_auth_and_audit(client, monkeypatch):
    assert client.get('/api/services').json()['ready']
    tunnel = {'name': 'ssh-home', 'server_host': 'frp.example.com', 'local_port': 22, 'remote_port': 6022}
    created = client.post('/api/tunnels', json=tunnel)
    assert created.status_code == 201
    identifier = created.json()['id']
    assert client.post('/api/tunnels', json=tunnel).status_code == 409
    assert client.put('/api/tunnels/' + identifier, json=dict(tunnel, local_port=23)).status_code == 200
    monkeypatch.setenv('R_LINK_FRPC_BINARY', str(Path('missing-frpc.exe').resolve()))
    assert client.post(f'/api/tunnels/{identifier}/start').status_code == 503
    assert client.get(f'/api/tunnels/{identifier}/logs').json() == {'logs': ''}
    assert client.post(f'/api/tunnels/{identifier}/stop').status_code == 200
    assert client.delete('/api/tunnels/' + identifier).status_code == 204
    assert client.get(f'/api/tunnels/{identifier}/logs').status_code == 404
    domain = {'hostname': 'App.Example.Com.', 'upstream_port': 8080}
    result = client.post('/api/domains', json=domain)
    assert result.status_code == 201
    identifier = result.json()['id']
    assert result.json()['hostname'] == 'app.example.com'
    assert client.post('/api/domains', json=domain).status_code == 409
    assert client.get(f'/api/domains/{identifier}/dns').status_code == 503
    assert client.post('/api/domains', json=dict(domain, hostname='*.example.com')).status_code == 422
    assert client.post('/api/domains', json=dict(domain, upstream_host='127.0.0.1; whoami')).status_code == 422
    monkeypatch.setenv('R_LINK_CADDY_BINARY', str(Path('missing-caddy.exe').resolve()))
    assert client.post('/api/domains/service/apply').status_code == 503
    assert client.delete('/api/domains/' + identifier).status_code == 204
    assert client.post('/api/domains/service/apply').json()['state'] == 'stopped'
    assert any(event['action'] == 'tunnel.save' for event in client.get('/api/audit').json())
    monkeypatch.setenv('R_LINK_API_TOKEN', 'private-key')
    assert client.get('/api/services').status_code == 401
    assert client.get('/api/services', headers={'Authorization': 'Bearer private-key'}).status_code == 200


def test_persistence_lock_and_unknown_database_version(tmp_path):
    first = ServiceState(tmp_path)
    item = first.save('domain', {'hostname': 'persist.example.com'})
    first.acquire()
    second = ServiceState(tmp_path)
    assert second.get('domain', item['id'])['hostname'] == 'persist.example.com'
    with pytest.raises(RuntimeError, match='one worker'):
        second.acquire()
    first.release()
    second.acquire()
    second.release()
    with first.db() as db:
        db.execute('PRAGMA user_version=999')
    with pytest.raises(RuntimeError, match='newer'):
        ServiceState(tmp_path)


@pytest.mark.asyncio
async def test_failed_second_worker_does_not_change_first_workers_process_records():
    first = Services()
    await first.start()
    first.state.save('process', {'pid': 123, 'created': 1, 'executable': 'fixture', 'cwd': 'fixture'}, 'caddy')
    second = Services()
    try:
        with pytest.raises(RuntimeError, match='one worker'):
            await second.start()
        await second.close()
        assert first.state.get('process', 'caddy')['pid'] == 123
        assert first.ready
    finally:
        first.state.delete('process', 'caddy')
        await first.close()


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'ftp://example.com/a', 'http://127.0.0.1/a',
    'http://169.254.169.254/a', 'http://[::1]/a', 'http://[::ffff:127.0.0.1]/a',
    'http://user:password@example.com/a', 'http://example.com:0/a', 'http://example.com/a#secret'])
def test_download_rejects_unsafe_urls(url):
    with pytest.raises(ValidationError):
        DownloadInput(url=url, name='file')


@pytest.mark.asyncio
async def test_dns_resolution_blocks_rebinding(monkeypatch):
    async def private(*args, **kwargs):
        return [{'host': '10.0.0.1'}]
    monkeypatch.setattr(aiohttp.resolver.DefaultResolver, 'resolve', private)
    resolver = PublicResolver()
    try:
        with pytest.raises(OSError, match='内网'):
            await resolver.resolve('public.example.com')
    finally:
        await resolver.close()


@pytest_asyncio.fixture
async def source(monkeypatch):
    monkeypatch.setenv('R_LINK_DOWNLOAD_ALLOWED_HOSTS', '127.0.0.1')
    body = b'0123456789' * 20000
    requests = []

    async def serve(request):
        requests.append(dict(request.headers))
        if request.path == '/redirect':
            raise web.HTTPFound('http://169.254.169.254/latest/meta-data/')
        offset = int(request.headers.get('Range', 'bytes=0-')[6:-1])
        if request.path == '/ignore-range':
            offset = 0
        headers = {'ETag': '"version1"', 'Content-Length': str(len(body) - offset)}
        if request.path == '/changed':
            headers['ETag'] = '"version2"'
        if offset:
            headers['Content-Range'] = f'bytes {offset}-{len(body)-1}/{len(body)}'
        if request.path == '/bad-range':
            headers['Content-Range'] = f'bytes 0-{len(body)-1}/{len(body)}'
        response = web.StreamResponse(status=206 if offset else 200, headers=headers)
        await response.prepare(request)
        try:
            for index in range(offset, len(body), 10000):
                await response.write(body[index:index + 10000])
                await asyncio.sleep(0.02)
        except (ConnectionResetError, aiohttp.ClientConnectionError):
            pass
        return response

    application = web.Application()
    application.router.add_get('/{tail:.*}', serve)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f'http://127.0.0.1:{port}', body, requests
    await runner.cleanup()


async def finished(manager, identifier):
    task = manager.tasks.get(identifier)
    if task:
        await asyncio.wait_for(task, 5)
    return manager.state.get('download', identifier)


@pytest.mark.asyncio
async def test_download_pause_resume_and_restart(tmp_path, source):
    base, body, requests = source
    state = ServiceState(tmp_path)
    manager = DownloadManager(state)
    item = await manager.create(DownloadInput(url=base + '/file', name='file.bin'))
    identifier = item['id']
    await asyncio.sleep(0.12)
    paused = await manager.action(identifier, 'pause')
    assert 0 < paused['downloaded'] < len(body)
    assert paused['state'] == 'paused'
    await manager.close()
    recovered = DownloadManager(ServiceState(tmp_path))
    await recovered.recover()
    assert not recovered.tasks  # deliberately paused work must stay paused
    await recovered.action(identifier, 'resume')
    result = await finished(recovered, identifier)
    assert result['state'] == 'completed'
    assert recovered.path(identifier, '.file').read_bytes() == body
    assert requests[-1]['Range'] == f'bytes={paused["downloaded"]}-'
    assert requests[-1]['If-Range'] == '"version1"'
    await recovered.action(identifier, 'delete')
    assert not state.list('download')
    await recovered.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('path,expected', [('/file', 'completed'), ('/ignore-range', 'completed'),
                                         ('/changed', 'failed'), ('/bad-range', 'failed')])
async def test_resume_validators_and_range_fallback(tmp_path, source, path, expected):
    base, body, _ = source
    state = ServiceState(tmp_path)
    manager = DownloadManager(state)
    item = state.save('download', {'url': base + path, 'name': 'a', 'state': 'running', 'downloaded': 10000,
                                   'total': len(body), 'validator': '"version1"', 'error': None})
    manager.path(item['id']).write_bytes(body[:10000])
    await manager.recover()
    result = await finished(manager, item['id'])
    assert result['state'] == expected
    if expected == 'completed':
        assert manager.path(item['id'], '.file').read_bytes() == body
    await manager.close()


@pytest.mark.asyncio
async def test_download_size_redirect_cancel_and_unsafe_file(tmp_path, source):
    base, _, _ = source
    manager = DownloadManager(ServiceState(tmp_path))
    manager.max_bytes = 100
    for path in ['/file', '/redirect']:
        item = await manager.create(DownloadInput(url=base + path, name='a'))
        assert (await finished(manager, item['id']))['state'] == 'failed'
        await manager.action(item['id'], 'cancel')
        assert not manager.path(item['id']).exists()
        await manager.action(item['id'], 'delete')
    item = manager.state.save('download', {'state': 'completed', 'name': 'a'})
    external = tmp_path / 'private'
    external.write_text('secret')
    os.link(external, manager.path(item['id'], '.file'))
    with pytest.raises(HTTPException) as error:
        manager.path(item['id'], '.file')
    assert error.value.status_code == 403
    await manager.close()


@pytest.mark.asyncio
async def test_process_lifecycle_redacts_logs_and_recovers_owned_pid(tmp_path):
    state = ServiceState(tmp_path)
    service = ManagedService(state, 'fixture')
    try:
        await service.start([sys.executable, '-u', '-c', 'import time; print("private-token", flush=True); time.sleep(30)'], secrets=('private-token',))
        assert service.status()['state'] == 'running'
        for _ in range(30):
            if '[redacted]' in service.logs():
                break
            await asyncio.sleep(0.05)
        assert '[redacted]' in service.logs()
        assert 'private-token' not in service.logs()
        await recover_processes(state)
        await asyncio.to_thread(service.process.wait, timeout=3)
        assert service.status()['state'] == 'error'
        assert state.list('process') == []
    finally:
        await service.stop()
    assert service.status()['state'] == 'stopped'


@pytest.mark.asyncio
async def test_recovery_never_kills_a_reused_pid(tmp_path):
    state = ServiceState(tmp_path)
    state.save('process', {'pid': os.getpid(), 'created': 0, 'executable': sys.executable, 'cwd': str(tmp_path)}, 'old')
    await recover_processes(state)
    assert state.list('process') == []


@pytest.mark.asyncio
async def test_failed_process_persistence_does_not_leave_a_child(tmp_path, monkeypatch):
    import core.managed_service as module
    state = ServiceState(tmp_path)
    service = ManagedService(state, 'fixture')
    real_popen = module.subprocess.Popen
    children = []
    def create(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        children.append(process)
        return process
    def no_space(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(module.subprocess, 'Popen', create)
    monkeypatch.setattr(state, 'save', no_space)
    with pytest.raises(OSError, match='disk full'):
        await service.start([sys.executable, '-c', 'import time; time.sleep(30)'])
    assert children[0].poll() is not None
    assert service.process is None


def test_tunnel_and_caddy_configuration(monkeypatch, tmp_path):
    item = TunnelInput(name='ssh', server_host='frps.example.com', local_port=22, remote_port=6000)
    config = frp_config(item.model_dump(), 'secret')
    assert config['transport']['tls']['enable']
    assert config['auth']['token'] == 'secret'
    assert 'token' not in item.model_dump()
    domain = DomainInput(hostname='test.example.com', upstream_host='::1', upstream_port=8080)
    config = caddy_config([domain.model_dump()], tmp_path)
    assert config['admin']['disabled']
    assert config['apps']['http']['servers']['rlink']['routes'][0]['handle'][0]['upstreams'][0]['dial'] == '[::1]:8080'
    monkeypatch.setenv('R_LINK_ACME_STAGING', 'true')
    assert 'staging' in json.dumps(caddy_config([domain.model_dump()], tmp_path))


@pytest.mark.asyncio
async def test_dns_is_scoped_to_stored_domain_and_payload_validated(tmp_path, monkeypatch):
    state = ServiceState(tmp_path)
    manager = DomainManager(state)
    item = await manager.save(DomainInput(hostname='app.example.com', upstream_port=8080, zone_id='a' * 32))
    calls = []
    async def provider(method, zone_id, path='', **kwargs):
        calls.append((method, zone_id, path, kwargs))
        return {'id': 'b' * 32, 'name': 'another.example.com'}
    monkeypatch.setattr(domains, 'cloudflare', provider)
    with pytest.raises(HTTPException) as exc:
        await manager.dns(item['id'], 'DELETE', record_id='b' * 32)
    assert exc.value.status_code == 403
    assert len(calls) == 1
    await manager.dns(item['id'], 'POST', data=DNSInput(type='A', content='203.0.113.1'))
    assert calls[-1][3]['json']['name'] == item['hostname']
    assert calls[-1][3]['json']['proxied'] is False
    with pytest.raises(HTTPException):
        DNSInput(type='AAAA', content='192.0.2.1').payload(item['hostname'])
