"""Domain bindings, Cloudflare DNS, and Caddy-managed HTTPS."""
import asyncio
import ipaddress
import os
import re
import socket
import ssl
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from core.devices import DeviceInput
from core.managed_service import ManagedService, executable, private_json
from core.service_state import now


class DomainInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    hostname: str = Field(min_length=3, max_length=253)
    upstream_host: str = Field(default='127.0.0.1', min_length=1, max_length=253)
    upstream_port: int = Field(ge=1, le=65535, strict=True)
    enabled: bool = True
    zone_id: str = Field(default='', pattern=r'^(?:[a-fA-F0-9]{32})?$')

    @field_validator('hostname')
    @classmethod
    def domain(cls, value):
        value = value.rstrip('.').lower().encode('idna').decode('ascii')
        if len(value) > 253 or '.' not in value or not re.fullmatch(r'[a-z0-9.-]+', value):
            raise ValueError('请输入完整域名，不支持通配符')
        DeviceInput.normalize_host(value)
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return value
        raise ValueError('请填写域名而非 IP 地址')

    @field_validator('upstream_host')
    @classmethod
    def upstream(cls, value):
        return DeviceInput.normalize_host(value)


class DNSInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    type: Literal['A', 'AAAA', 'CNAME']
    content: str = Field(min_length=1, max_length=253)
    ttl: int = Field(default=1, ge=1, le=86400, strict=True)

    @field_validator('ttl')
    @classmethod
    def ttl_range(cls, value):
        if value != 1 and value < 60:
            raise ValueError('TTL 应为 1（自动）或 60–86400 秒')
        return value

    def payload(self, hostname):
        try:
            if self.type in ('A', 'AAAA'):
                address = ipaddress.ip_address(self.content)
                if address.version != (4 if self.type == 'A' else 6):
                    raise ValueError()
                content = str(address)
            else:
                content = DomainInput.domain(self.content)
        except ValueError:
            raise HTTPException(422, 'DNS 记录内容与类型不匹配') from None
        return {'name': hostname, 'type': self.type, 'content': content, 'ttl': self.ttl, 'proxied': False}


def caddy_config(items, directory):
    routes = []
    for item in items:
        if not item['enabled']:
            continue
        host = item['upstream_host']
        dial = f'[{host}]:{item["upstream_port"]}' if ':' in host else f'{host}:{item["upstream_port"]}'
        routes.append({'match': [{'host': [item['hostname']]}],
                       'handle': [{'handler': 'reverse_proxy', 'upstreams': [{'dial': dial}]}], 'terminal': True})
    config = {'admin': {'disabled': True}, 'storage': {'module': 'file_system', 'root': str(directory)},
              'apps': {'http': {'servers': {'rlink': {'listen': [':443'], 'routes': routes}}}}}
    # An explicit staging CA prevents tests/development from consuming production limits.
    if os.getenv('R_LINK_ACME_STAGING', '').lower() in ('1', 'true'):
        config['apps']['tls'] = {'automation': {'policies': [{'issuers': [
            {'module': 'acme', 'ca': 'https://acme-staging-v02.api.letsencrypt.org/directory'}]}]}}
    return config


async def cloudflare(method, zone_id, path='', **kwargs):
    token = os.getenv('R_LINK_CLOUDFLARE_TOKEN')
    if not token or not zone_id:
        raise HTTPException(503, '需要域名的 Zone ID 和服务端 R_LINK_CLOUDFLARE_TOKEN（DNS 编辑权限）')
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.request(method, f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records{path}',
                                            headers={'Authorization': 'Bearer ' + token}, **kwargs)
        payload = response.json()
        if not response.is_success or not payload.get('success'):
            raise HTTPException(502, f'Cloudflare 操作失败（HTTP {response.status_code}），请检查区域和权限')
        return payload['result']
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(502, '无法连接 Cloudflare DNS 服务') from None


class DomainManager:
    def __init__(self, state):
        self.state = state
        self.process = ManagedService(state, 'caddy')
        self.lock = asyncio.Lock()
        self.applied = None

    def status(self):
        current = self.bindings()
        return dict(self.process.status(), pending_changes=current != self.applied,
                    dns_configured=bool(os.getenv('R_LINK_CLOUDFLARE_TOKEN')))

    def bindings(self):
        return [{key: item[key] for key in DomainInput.model_fields} for item in self.state.list('domain')]

    async def save(self, data, identifier=None):
        async with self.lock:
            items = self.state.list('domain')
            if identifier:
                self.state.get('domain', identifier)
            elif len(items) >= 100:
                raise HTTPException(409, '域名数量最多为 100')
            if any(item['hostname'] == data.hostname and item['id'] != identifier for item in items):
                raise HTTPException(409, '此域名已存在')
            item = self.state.save('domain', data.model_dump(), identifier)
            self.state.audit('domain.save', item['id'])
            return item

    async def delete(self, identifier):
        async with self.lock:
            self.state.delete('domain', identifier)
            self.state.audit('domain.delete', identifier)

    async def apply(self):
        async with self.lock:
            bindings = self.bindings()
            if not any(item['enabled'] for item in bindings):
                await self.process.stop()
                self.applied = bindings
            else:
                binary = executable('R_LINK_CADDY_BINARY', 'caddy')
                config = self.process.directory / 'caddy.json'
                candidate = self.process.directory / 'candidate.json'
                private_json(candidate, caddy_config(bindings, self.state.root / 'certificates'))
                # Validate through a separately owned short-lived process before stopping a working service.
                validator = ManagedService(self.state, 'caddy-validate')
                try:
                    try:
                        await validator.start([binary, 'validate', '--config', str(candidate)])
                    except HTTPException:
                        if not validator.process or validator.process.poll() != 0:
                            raise HTTPException(422, 'Caddy 配置验证失败，请检查证书目录和域名配置') from None
                    if validator.process:
                        try:
                            code = await asyncio.to_thread(validator.process.wait, timeout=15)
                        except Exception:
                            raise HTTPException(504, 'Caddy 配置验证超时') from None
                        if code != 0:
                            raise HTTPException(422, 'Caddy 配置验证失败')
                finally:
                    await validator.stop()
                previous = config.read_bytes() if config.exists() else None
                was_running = self.process.status()['state'] == 'running'
                await self.process.stop()
                candidate.replace(config)
                try:
                    await self.process.start([binary, 'run', '--config', str(config)])
                except HTTPException:
                    if previous:
                        config.write_bytes(previous)
                        if was_running:
                            try:
                                await self.process.start([binary, 'run', '--config', str(config)])
                            except HTTPException:
                                pass
                    raise
                self.applied = bindings
            self.state.save('settings', {'enabled': any(item['enabled'] for item in bindings), 'bindings': bindings}, 'https')
            self.state.audit('domain.apply', 'https')
            return self.status()

    async def stop(self):
        async with self.lock:
            await self.process.stop()
            self.state.save('settings', {'enabled': False, 'bindings': self.applied or []}, 'https')
            self.state.audit('domain.stop', 'https')
            return self.status()

    async def recover(self):
        settings = next((item for item in self.state.list('settings') if item['id'] == 'https'), None)
        if settings and settings['enabled']:
            # Restore only the last explicitly applied bindings, never unreviewed edits.
            config = self.process.directory / 'caddy.json'
            private_json(config, caddy_config(settings['bindings'], self.state.root / 'certificates'))
            try:
                await self.process.start([executable('R_LINK_CADDY_BINARY', 'caddy'), 'run', '--config', str(config)])
                self.applied = settings['bindings']
            except HTTPException as exc:
                self.process.error = exc.detail

    async def check(self, identifier):
        item = self.state.get('domain', identifier)
        host = item['hostname']
        result = {'checked_at': now(), 'addresses': [], 'tls_valid': False, 'certificate_expires_at': None, 'error': None}
        try:
            records = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM), 5)
            result['addresses'] = sorted({entry[4][0] for entry in records})
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, 443, ssl=ssl.create_default_context(), server_hostname=host), 8)
            try:
                certificate = writer.get_extra_info('ssl_object').getpeercert()
                result.update(tls_valid=True, certificate_expires_at=certificate.get('notAfter'))
            finally:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), 2)
                except (OSError, asyncio.TimeoutError):
                    pass
        except (OSError, asyncio.TimeoutError):
            result['error'] = '域名未解析、HTTPS 无法连接或证书校验失败'
        # Probe results are returned independently, so slow checks cannot overwrite edits.
        return result

    async def dns(self, identifier, method='GET', data=None, record_id=None):
        item = self.state.get('domain', identifier)
        if method == 'GET':
            records = await cloudflare('GET', item['zone_id'], params={'name': item['hostname'], 'per_page': 100})
            return [{key: record.get(key) for key in ('id', 'type', 'name', 'content', 'ttl', 'proxied')} for record in records]
        if method == 'POST':
            payload = data.payload(item['hostname'])
            result = await cloudflare('POST', item['zone_id'], json=payload)
        else:
            if not re.fullmatch(r'[a-fA-F0-9]{32}', record_id or ''):
                raise HTTPException(400, 'DNS 记录编号无效')
            record = await cloudflare('GET', item['zone_id'], '/' + record_id)
            if record['name'].rstrip('.').lower() != item['hostname']:
                raise HTTPException(403, '该 DNS 记录不属于此域名')
            result = await cloudflare('DELETE', item['zone_id'], '/' + record_id)
        self.state.audit('domain.dns.' + method.lower(), identifier)
        return result
