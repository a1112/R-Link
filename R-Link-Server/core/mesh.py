"""Validated NetBird control-plane adapter. No virtual peers are fabricated locally."""
import ipaddress
import json
import os
import re
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.devices import DeviceInput

ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
MAX_RESPONSE = 2 * 1024 * 1024
MANAGED_POLICY_DESCRIPTION = 'R-Link managed policy'


def safe_id(value: str) -> str:
    if not ID_RE.fullmatch(value):
        raise HTTPException(400, '无效的组网资源编号')
    return value


def configuration():
    url = os.getenv('R_LINK_NETBIRD_URL', '').strip().rstrip('/')
    token = os.getenv('R_LINK_NETBIRD_TOKEN', '')
    if not url or not token:
        raise HTTPException(503, '请设置 R_LINK_NETBIRD_URL 和 R_LINK_NETBIRD_TOKEN')
    try:
        parsed = urlsplit(url)
        if (not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password
                or parsed.scheme not in ('http', 'https') or '\\' in url
                or any(ord(c) < 33 for c in url)
                or (parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'))):
            raise ValueError()
        _ = parsed.port
    except ValueError:
        raise HTTPException(503, 'NetBird 地址必须为 HTTPS 源地址；HTTP 仅限本机回环') from None
    return url, token


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class GroupInput(Input):
    name: str = Field(min_length=1, max_length=80)
    peers: list[str] = Field(default_factory=list, max_length=256)

    @field_validator('peers')
    @classmethod
    def ids(cls, values):
        return [safe_id(value) for value in values]


class PeerInput(Input):
    name: str = Field(min_length=1, max_length=80)


class SetupKeyInput(Input):
    name: str = Field(min_length=1, max_length=80)
    type: Literal['one-off', 'reusable'] = 'one-off'
    expires_in: int = Field(default=86400, ge=86400, le=31536000, strict=True)
    auto_groups: list[str] = Field(min_length=1, max_length=32)
    usage_limit: int = Field(default=1, ge=0, le=1000, strict=True)
    ephemeral: bool = False

    @field_validator('auto_groups')
    @classmethod
    def ids(cls, values):
        return [safe_id(value) for value in values]

    @model_validator(mode='after')
    def limit_one_off(self):
        if self.type == 'one-off' and self.usage_limit not in (0, 1):
            raise ValueError('单次密钥不能设置多次使用')
        return self


class PolicyInput(Input):
    name: str = Field(min_length=1, max_length=80)
    source_group: str
    destination_group: str
    protocol: Literal['all', 'tcp', 'udp', 'icmp'] = 'all'
    ports: list[int] = Field(default_factory=list, max_length=32)
    enabled: bool = True
    bidirectional: bool = False

    @field_validator('source_group', 'destination_group')
    @classmethod
    def group_id(cls, value):
        return safe_id(value)

    @field_validator('ports')
    @classmethod
    def valid_ports(cls, values):
        if any(type(value) is not int or value < 1 or value > 65535 for value in values):
            raise ValueError('端口必须在 1–65535 范围内')
        return values

    @model_validator(mode='after')
    def ports_match_protocol(self):
        if self.ports and self.protocol not in ('tcp', 'udp'):
            raise ValueError('只有 TCP/UDP 策略可指定端口')
        return self

    def payload(self):
        rule = {'name': self.name, 'description': '', 'enabled': self.enabled,
                'action': 'accept', 'bidirectional': self.bidirectional, 'protocol': self.protocol,
                'sources': [self.source_group], 'destinations': [self.destination_group]}
        if self.ports:
            rule['ports'] = [str(port) for port in self.ports]
        return {'name': self.name, 'description': MANAGED_POLICY_DESCRIPTION,
                'enabled': self.enabled, 'rules': [rule]}


class NetworkInput(Input):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default='', max_length=500)


class ResourceInput(Input):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default='', max_length=500)
    address: str = Field(min_length=1, max_length=253)
    enabled: bool = True
    groups: list[str] = Field(min_length=1, max_length=32)

    @field_validator('address')
    @classmethod
    def address_valid(cls, value):
        try:
            return str(ipaddress.ip_network(value, strict=False))
        except ValueError:
            if value.startswith('*.'):
                return '*.' + DeviceInput.normalize_host(value[2:])
            return DeviceInput.normalize_host(value)

    @field_validator('groups')
    @classmethod
    def ids(cls, values):
        return [safe_id(value) for value in values]


class RouterInput(Input):
    peer: str | None = None
    peer_groups: list[str] = Field(default_factory=list, max_length=32)
    metric: int = Field(default=100, ge=1, le=9999, strict=True)
    masquerade: bool = True
    enabled: bool = True

    @model_validator(mode='after')
    def one_target(self):
        if bool(self.peer) == bool(self.peer_groups):
            raise ValueError('必须且只能指定一个节点或至少一个节点组')
        if self.peer:
            safe_id(self.peer)
        for value in self.peer_groups:
            safe_id(value)
        return self

    def payload(self):
        data = self.model_dump(exclude_none=True)
        if self.peer:
            data.pop('peer_groups')
        else:
            data.pop('peer', None)
        return data


class NetBird:
    def __init__(self, transport=None):
        self.transport = transport

    async def request(self, method: str, path: str, body=None):
        url, token = configuration()
        if not path.startswith('/api/') or not re.fullmatch(r'/[A-Za-z0-9/_-]+', path):
            raise HTTPException(400, '无效的 NetBird API 路径')
        try:
            async with httpx.AsyncClient(timeout=12, trust_env=False, follow_redirects=False,
                                         transport=self.transport) as client:
                async with client.stream(method, url + path, json=body,
                                         headers={'Authorization': 'Token ' + token, 'Accept': 'application/json'}) as response:
                    if response.status_code == 404:
                        raise HTTPException(404, 'NetBird 资源不存在')
                    if response.status_code == 409:
                        raise HTTPException(409, 'NetBird 资源冲突')
                    if response.status_code in (400, 422):
                        raise HTTPException(422, 'NetBird 拒绝了配置，请检查组、节点和路由参数')
                    if response.status_code in (401, 403):
                        raise HTTPException(502, 'NetBird 访问令牌无效或权限不足')
                    if response.status_code < 200 or response.status_code >= 300:
                        raise HTTPException(502, f'NetBird 请求失败（HTTP {response.status_code}）')
                    if response.status_code == 204:
                        return None
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > MAX_RESPONSE:
                            raise HTTPException(502, 'NetBird 返回的数据过大')
                    result = json.loads(payload)
                    if not isinstance(result, (dict, list)):
                        raise ValueError()
                    return result
        except HTTPException:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, ValueError):
            raise HTTPException(502, 'NetBird 管理服务不可用或返回了无效响应') from None


netbird = NetBird()


def without_key(item):
    if isinstance(item, list):
        return [without_key(entry) for entry in item]
    if isinstance(item, dict):
        return {key: without_key(value) for key, value in item.items() if key != 'key'}
    return item
