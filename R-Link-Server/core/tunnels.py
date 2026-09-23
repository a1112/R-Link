"""FRP client configuration and lifecycle, one owned process per tunnel."""
import asyncio
import os
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from core.devices import DeviceInput
from core.managed_service import ManagedService, executable, private_json, child_environment


class TunnelInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    server_host: str = Field(min_length=1, max_length=253)
    server_port: int = Field(default=7000, ge=1, le=65535, strict=True)
    local_host: str = Field(default='127.0.0.1', min_length=1, max_length=253)
    local_port: int = Field(ge=1, le=65535, strict=True)
    remote_port: int = Field(ge=1, le=65535, strict=True)
    protocol: Literal['tcp', 'udp'] = 'tcp'
    token_env: str = Field(default='R_LINK_FRP_TOKEN', pattern=r'^R_LINK_FRP_TOKEN(?:_[A-Z0-9_]+)?$')
    autostart: bool = False

    @field_validator('server_host', 'local_host')
    @classmethod
    def host(cls, value):
        return DeviceInput.normalize_host(value)


def frp_config(item, token):
    return {'serverAddr': item['server_host'], 'serverPort': item['server_port'],
            'auth': {'method': 'token', 'token': token}, 'transport': {'tls': {'enable': True}},
            'loginFailExit': True, 'log': {'to': 'console', 'level': 'info', 'disablePrintColor': True},
            'proxies': [{'name': item['name'], 'type': item['protocol'], 'localIP': item['local_host'],
                         'localPort': item['local_port'], 'remotePort': item['remote_port']}]}


class TunnelManager:
    def __init__(self, state):
        self.state = state
        self.processes = {}
        self.lock = asyncio.Lock()

    def process(self, identifier):
        self.state.get('tunnel', identifier)
        if identifier not in self.processes:
            self.processes[identifier] = ManagedService(self.state, 'frp-' + identifier)
        return self.processes[identifier]

    def list(self):
        return [dict(item, runtime=self.process(item['id']).status()) for item in self.state.list('tunnel')]

    async def save(self, data, identifier=None):
        async with self.lock:
            if identifier:
                self.state.get('tunnel', identifier)
                if self.process(identifier).status()['state'] == 'running':
                    raise HTTPException(409, '请先停止隧道再修改配置')
            items = self.state.list('tunnel')
            if not identifier and len(items) >= 64:
                raise HTTPException(409, '最多支持 64 个隧道')
            for item in items:
                if item['id'] == identifier:
                    continue
                if item['name'] == data.name or (item['server_host'], item['server_port'], item['protocol'], item['remote_port']) == (
                        data.server_host, data.server_port, data.protocol, data.remote_port):
                    raise HTTPException(409, '隧道名称或服务器上的协议/端口重复')
            item = self.state.save('tunnel', data.model_dump(), identifier)
            self.state.audit('tunnel.save', item['id'])
            return dict(item, runtime=self.process(item['id']).status())

    async def start(self, identifier):
        async with self.lock:
            item = self.state.get('tunnel', identifier)
            process = self.process(identifier)
            if process.status()['state'] == 'running':
                return process.status()
            binary = executable('R_LINK_FRPC_BINARY', 'frpc')
            token = os.getenv(item['token_env'])
            if not token:
                raise HTTPException(503, f'请在服务端设置 {item["token_env"]}')
            config = process.directory / 'frpc.json'
            private_json(config, frp_config(item, token))
            try:
                result = await process.start([binary, '-c', str(config)], secrets=(token,), env=child_environment(direct_network=True))
            except BaseException:
                await process.stop()
                config.unlink(missing_ok=True)
                raise
            self.state.audit('tunnel.start', identifier)
            return result

    async def stop(self, identifier, delete=False):
        async with self.lock:
            process = self.process(identifier)
            await process.stop()
            (process.directory / 'frpc.json').unlink(missing_ok=True)
            if delete:
                self.state.delete('tunnel', identifier)
                self.processes.pop(identifier, None)
            self.state.audit('tunnel.delete' if delete else 'tunnel.stop', identifier)
            return process.status()

    async def recover(self):
        for item in self.state.list('tunnel'):
            # Remove a credential-bearing config left by an unclean exit.
            (self.process(item['id']).directory / 'frpc.json').unlink(missing_ok=True)
            if item['autostart']:
                try:
                    await self.start(item['id'])
                except HTTPException as exc:
                    self.process(item['id']).error = exc.detail

    async def close(self):
        for identifier, process in self.processes.items():
            await process.stop()
            (process.directory / 'frpc.json').unlink(missing_ok=True)
