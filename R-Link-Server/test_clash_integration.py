"""Opt-in real Mihomo acceptance, isolated loopback only; no system proxy changes.

R_LINK_RUN_CLASH_INTEGRATION=1 R_LINK_MIHOMO_BINARY=/path/to/mihomo \
    python -m pytest R-Link-Server/test_clash_integration.py -q
"""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from fastapi import FastAPI
import httpx
import pytest

from api.clash import router
from core.auth import require_auth
from core.clash import ClashManager
from core.service_state import ServiceState

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    os.getenv('R_LINK_RUN_CLASH_INTEGRATION') != '1', reason='Opt-in real Mihomo integration')]


async def test_real_mihomo_api_and_http_proxy_are_owned(tmp_path, monkeypatch):
    configured = os.getenv('R_LINK_MIHOMO_BINARY')
    if not configured or not Path(configured).is_file():
        pytest.fail('Set R_LINK_MIHOMO_BINARY to an installed Mihomo executable')
    state = ServiceState(tmp_path)
    manager = ClashManager(state)
    app = FastAPI()
    app.include_router(router)
    app.state.services = SimpleNamespace(ready=True, clash=manager)
    app.dependency_overrides[require_auth] = lambda: {'id': 'integration-operator'}
    group = '真实测试 中文'
    payload = b'actual-mihomo-http-proxy'
    provider_body = b'proxies:\n  - name: local-provider-node\n    type: http\n    server: 127.0.0.1\n    port: 33333\n'
    provider_requests = []

    async def upstream(reader, writer):
        try:
            request = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 3)
            body = payload
            # Mihomo treats a sub-millisecond zero result as a failed test.
            # A deterministic local delay makes the health result observable.
            if b'/latency' in request.split(b'\r\n')[0]:
                await asyncio.sleep(.03)
            if b'/provider' in request.split(b'\r\n')[0]:
                provider_requests.append(request)
                body = provider_body
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode()
                         + b'\r\nConnection: close\r\n\r\n' + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(upstream, '127.0.0.1', 0)
    upstream_port = server.sockets[0].getsockname()[1]
    monkeypatch.setenv('R_LINK_CLASH_TEST_URL', f'http://127.0.0.1:{upstream_port}/latency')
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://rlink.test') as api:
            response = await api.post('/api/clash/profiles', json={'name': 'isolated acceptance', 'content': f'''
mode: rule
log-level: warning
mixed-port: {upstream_port}
port: {upstream_port}
socks-port: {upstream_port}
proxies: []
proxy-providers:
  本机提供商:
    type: http
    url: http://127.0.0.1:{upstream_port}/provider
    interval: 3600
    health-check:
      enable: false
proxy-groups:
  - name: "{group}"
    type: select
    proxies: [DIRECT, REJECT]
rules:
  - "MATCH,{group}"
'''})
            assert response.status_code == 201, response.text
            profile = response.json()
            assert 'content' not in profile and 'path' not in profile
            started = await api.post('/api/clash/managed/start', json={'profile_id': profile['id']})
            assert started.status_code == 200, started.text
            process = manager.process.process
            assert process is not None and process.poll() is None
            # A running process alone is insufficient; await authenticated API.
            for _ in range(30):
                status = (await api.get('/api/clash/status')).json()
                if status['connected']:
                    break
                await asyncio.sleep(.1)
            assert status['connected'], status
            assert status['version'] and status['managed']['profile_id'] == profile['id']
            assert status['controller_url'].startswith('http://127.0.0.1:')
            async with httpx.AsyncClient(trust_env=False) as unauthenticated:
                assert (await unauthenticated.get(status['controller_url'] + '/version')).status_code == 401
            assert 'secret' not in status
            configs = (await api.get('/api/clash/configs')).json()
            assert configs['mixed_port'] > 0 and configs['mixed_port'] != upstream_port
            assert configs['port'] == 0 and configs['socks_port'] == 0
            assert configs['allow_lan'] is False and configs['tun_enabled'] is False
            patched = await api.patch('/api/clash/configs', json={'mode': 'direct', 'log_level': 'error'})
            assert patched.status_code == 200 and patched.json()['mode'] == 'direct'
            await api.patch('/api/clash/configs', json={'mode': 'rule'})
            proxies = (await api.get('/api/clash/proxies')).json()['proxies']
            assert group in proxies and proxies[group]['now'] == 'DIRECT'
            group_path = '/api/clash/proxies/' + quote(group, safe='')
            assert (await api.put(group_path, json={'name': 'REJECT'})).status_code == 204
            assert (await api.get('/api/clash/proxies')).json()['proxies'][group]['now'] == 'REJECT'
            assert (await api.put(group_path, json={'name': 'DIRECT'})).status_code == 204
            latency = await api.get(group_path + '/delay')
            assert latency.status_code == 200 and latency.json()['delay'] >= 0, latency.text
            assert (await api.get('/api/clash/rules')).json()['rules'][-1]['proxy'] == group
            # Actual HTTP bytes must traverse the owned proxy, not a fixture API.
            async with httpx.AsyncClient(proxy=f"http://127.0.0.1:{configs['mixed_port']}", trust_env=False) as proxied:
                response = await proxied.get(f'http://127.0.0.1:{upstream_port}/acceptance')
            assert response.status_code == 200 and response.content == payload
            connections = await api.get('/api/clash/connections')
            assert connections.status_code == 200 and 'downloadTotal' in connections.json()
            assert (await api.delete('/api/clash/connections')).status_code == 204
            providers = (await api.get('/api/clash/providers/proxies')).json()['providers']
            assert providers['本机提供商']['proxies'][0]['name'] == 'local-provider-node'
            assert 'url' not in providers['本机提供商']
            before_refresh = len(provider_requests)
            refreshed = await api.put('/api/clash/providers/proxies/' + quote('本机提供商', safe=''))
            assert refreshed.status_code == 204 and len(provider_requests) > before_refresh
            assert (await api.delete('/api/clash/profiles/' + profile['id'])).status_code == 409
            stopped = await api.post('/api/clash/managed/stop')
            assert stopped.status_code == 200 and stopped.json()['state'] == 'stopped'
            assert process.poll() is not None
            assert not (manager.process.directory / 'mihomo.yaml').exists()
            assert (await api.get('/api/clash/status')).json()['connected'] is False
            assert (await api.delete('/api/clash/profiles/' + profile['id'])).status_code == 204
    finally:
        await manager.close()
        server.close()
        await server.wait_closed()
