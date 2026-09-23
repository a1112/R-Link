"""Opt-in real binary tests: loopback only, no public DNS or certificate issuance.

R_LINK_RUN_INTEGRATION=1 python -m pytest R-Link-Server/test_services_integration.py -q
"""
import asyncio
import os
import socket
from pathlib import Path

import httpx
import pytest

from core.service_state import ServiceState
from core.managed_service import ManagedService, private_json
from core.tunnels import TunnelManager, TunnelInput
from core.domains import DomainManager, DomainInput, caddy_config
from core import domains

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(os.getenv('R_LINK_RUN_INTEGRATION') != '1', reason='Opt-in real frp/Caddy integration')]
BIN = Path(__file__).resolve().parents[1] / 'binaries'


def binary(name):
    result = BIN / (name + ('.exe' if os.name == 'nt' else ''))
    if not result.is_file():
        pytest.fail('Run scripts/install-service-tools.py first')
    return str(result)


def available_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


async def test_real_frp_forwards_bytes_and_stops_its_process(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_FRPC_BINARY', binary('frpc'))
    monkeypatch.setenv('R_LINK_FRP_TOKEN', 'integration-test-only-token')
    state = ServiceState(tmp_path)
    frps = ManagedService(state, 'fixture-frps')
    manager = TunnelManager(state)

    async def echo(reader, writer):
        try:
            data = await reader.read(1024)
            writer.write(data)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(echo, '127.0.0.1', 0)
    local_port = server.sockets[0].getsockname()[1]
    control, remote = available_port(), available_port()
    config = frps.directory / 'frps.json'
    private_json(config, {'bindAddr': '127.0.0.1', 'bindPort': control, 'proxyBindAddr': '127.0.0.1',
                          'auth': {'method': 'token', 'token': 'integration-test-only-token'}})
    try:
        await frps.start([binary('frps'), '-c', str(config)])
        item = await manager.save(TunnelInput(name='integration-echo', server_host='127.0.0.1',
                                               server_port=control, local_port=local_port, remote_port=remote))
        await manager.start(item['id'])
        for _ in range(60):
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', remote), 0.3)
                break
            except (OSError, asyncio.TimeoutError):
                if manager.process(item['id']).status()['state'] != 'running':
                    pytest.fail(manager.process(item['id']).logs())
                await asyncio.sleep(0.1)
        else:
            pytest.fail(manager.process(item['id']).logs())
        writer.write(b'real-frp-tunnel')
        await writer.drain()
        assert await asyncio.wait_for(reader.read(1024), 5) == b'real-frp-tunnel'
        writer.close()
        await writer.wait_closed()
        process = manager.process(item['id']).process
        await manager.stop(item['id'])
        assert process.poll() is not None
        assert not (manager.process(item['id']).directory / 'frpc.json').exists()
    finally:
        await manager.close()
        await frps.stop()
        server.close()
        await server.wait_closed()


async def test_real_caddy_validates_applies_proxies_and_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_CADDY_BINARY', binary('caddy'))
    state = ServiceState(tmp_path)
    manager = DomainManager(state)
    proxy_port = available_port()

    async def upstream(reader, writer):
        try:
            await reader.readuntil(b'\r\n\r\n')
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 12\r\nConnection: close\r\n\r\nactual-proxy')
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(upstream, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    await manager.save(DomainInput(hostname='integration.example.invalid', upstream_port=port))
    # Exercise the production JSON schema and validation command first. The run
    # configuration disables automatic HTTPS, so no certificate requests occur.
    def local_config(items, directory):
        result = caddy_config(items, directory)
        config = result['apps']['http']['servers']['rlink']
        config.update(listen=[f'127.0.0.1:{proxy_port}'], automatic_https={'disable': True})
        return result
    monkeypatch.setattr(domains, 'caddy_config', local_config)
    try:
        result = await manager.apply()
        assert result['state'] == 'running'
        assert not result['pending_changes']
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(f'http://127.0.0.1:{proxy_port}', headers={'Host': 'integration.example.invalid'})
        assert response.text == 'actual-proxy'
        # Unapplied changes stay pending after service restart.
        await manager.save(DomainInput(hostname='pending.example.invalid', upstream_port=port))
        await manager.process.stop()
        restored = DomainManager(state)
        try:
            await restored.recover()
            assert restored.status()['state'] == 'running'
            assert restored.status()['pending_changes']
            await restored.stop()
        finally:
            await restored.process.stop()
    finally:
        await manager.process.stop()
        server.close()
        await server.wait_closed()
