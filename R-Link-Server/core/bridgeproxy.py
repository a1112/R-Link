"""Bounded, credential-owning access to an explicitly configured local Core.

This adapter controls the server's machine. It never discovers or installs a
Core, changes network settings itself, or treats a browser's host as local.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable
from typing import Any

import httpx

CONTRACT = json.loads((Path(__file__).resolve().parents[2] / 'contracts' /
                       'bridgeproxy-v1.json').read_text(encoding='utf-8'))
MAX_REQUEST_BYTES = CONTRACT['maximum_request_bytes']
MAX_RESPONSE_BYTES = CONTRACT['maximum_response_bytes']
REQUEST_DEADLINE_SECONDS = 10
MAX_CONCURRENT_REQUESTS = 8

READ_PATHS = tuple(route['path'][3:].replace('{id}', '{identifier}')
                   for route in CONTRACT['routes'] if route['method'] == 'GET'
                   and route['scope'] == 'read')
WRITE_ROUTES = tuple((route['method'], route['path'][3:].replace('{id}', '{identifier}'))
                     for route in CONTRACT['routes'] if route['method'] != 'GET')
_IDENTIFIER = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
_TOKEN = re.compile(r'[0-9a-fA-F]{64}\Z')
_ENDPOINT = re.compile(r'http://(?:127\.0\.0\.1|localhost):([0-9]{1,5})/?\Z')
_SECRET_KEYS = frozenset({
    'token', 'readtoken', 'controltoken', 'apisecret', 'secret', 'password',
    'privatekey', 'certificate', 'tlsidentity', 'customjson', 'authorization',
    'cookie', 'accesstoken', 'refreshtoken', 'clientsecret', 'pollsecret',
})


@dataclass
class CoreResponse:
    status: int
    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


def failure(status: int, code: str, message: str) -> CoreResponse:
    return CoreResponse(status, {'api_version': 'v1', 'error': {
        'status': status, 'code': code, 'message': message,
    }})


def allowed_route(method: str, path: str) -> bool:
    """No URL joins, encoded path segments, queries, or caller-defined commands."""
    if any(char in path for char in ('%', '?', '#', '\\')):
        return False
    routes = ((('GET', item) for item in READ_PATHS) if method == 'GET'
              else iter(WRITE_ROUTES))
    for expected_method, template in routes:
        if expected_method != method:
            continue
        if '{identifier}' not in template:
            if path == template:
                return True
            continue
        prefix, suffix = template.split('{identifier}')
        if not path.startswith(prefix) or (suffix and not path.endswith(suffix)):
            continue
        identifier = path[len(prefix):len(path) - len(suffix) if suffix else None]
        if _IDENTIFIER.fullmatch(identifier):
            return True
    return False


def _key(value: str) -> str:
    return re.sub('[^a-z0-9]', '', value.lower())


def _request_secrets(value: Any, depth: int = 0) -> list[str]:
    if depth > 32:
        return []
    if isinstance(value, dict):
        found = [item for key, item in value.items()
                 if (_key(key) in _SECRET_KEYS or _key(key) == 'verificationcode')
                 and isinstance(item, str) and item]
        return found + [secret for item in value.values()
                        for secret in _request_secrets(item, depth + 1)]
    if isinstance(value, list):
        return [secret for item in value for secret in _request_secrets(item, depth + 1)]
    return []


def _redact(value: Any, secrets: tuple[str, ...], allow_sas: bool, depth: int = 0,
            *, schema: bool = False, properties: bool = False) -> Any:
    if depth > 32:
        raise ValueError('Response nesting limit exceeded')
    if isinstance(value, dict):
        return {key: _redact(item, secrets, allow_sas, depth + 1,
                             schema=schema, properties=key == 'properties')
                for key, item in value.items()
                if (schema and properties) or (
                    _key(key) not in _SECRET_KEYS
                    and (allow_sas or _key(key) != 'verificationcode'))}
    if isinstance(value, list):
        return [_redact(item, secrets, allow_sas, depth + 1, schema=schema) for item in value]
    if isinstance(value, str):
        value.encode('utf-8')
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[redacted]')
        # Defensive removal of inline bearer values and URL credentials in logs.
        value = re.sub(r'(?i)\bbearer\s+[^\s"<>]+', 'Bearer [redacted]', value)
        value = re.sub(r'(?i)(https?://)[^\s/@]+:[^\s/@]+@', r'\1[redacted]@', value)
    return value


def _strict_json(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            key.encode('utf-8')
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError('Nonfinite JSON value')

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Nonfinite JSON value')
        return result

    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=invalid_constant, parse_float=finite_float)


class BridgeProxy:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        raw_endpoint = os.getenv('R_LINK_BRIDGEPROXY_URL', '').strip()
        match = _ENDPOINT.fullmatch(raw_endpoint)
        self.endpoint = (f'http://127.0.0.1:{int(match[1])}'
                         if match and 1 <= int(match[1]) <= 65535 else None)
        read = os.getenv('R_LINK_BRIDGEPROXY_READ_TOKEN', '').strip()
        control = os.getenv('R_LINK_BRIDGEPROXY_CONTROL_TOKEN', '').strip()
        self._read = read if _TOKEN.fullmatch(read) else ''
        self._control = control if _TOKEN.fullmatch(control) else ''
        self._reason = ('not_configured' if not raw_endpoint else
                        'invalid_endpoint' if not self.endpoint else
                        'read_credential_missing' if not read else
                        'invalid_read_credential' if not self._read else None)
        self._control_reason = ('control_credential_missing' if not control else
                                'invalid_control_credential' if not self._control else None)
        self._client = httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(5), limits=httpx.Limits(
                max_connections=MAX_CONCURRENT_REQUESTS, max_keepalive_connections=0),
        )
        self._slots = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._closed = False

    def adapter(self) -> CoreResponse:
        return CoreResponse(200, {'api_version': 'v1', 'data': {
            'target': 'server', 'endpoint_scope': 'server-loopback',
            'configured': self._reason is None,
            'control_configured': self._reason is None and not self._control_reason,
            'endpoint': self.endpoint, 'state': 'unobserved' if not self._reason else 'unavailable',
            'reason': self._reason, 'control_reason': self._control_reason,
            'message': '此目标为 R-Link 服务端所在机器，不是当前浏览器或桌面电脑。',
        }})

    async def close(self):
        self._closed = True
        await self._client.aclose()

    async def request(self, method: str, path: str, *, body: bytes = b'',
                      if_match: str | None = None, idempotency_key: str | None = None,
                      control: bool = False, allow_sas: bool = False,
                      authorize: Callable[[], None] | None = None) -> CoreResponse:
        if not allowed_route(method, path) or (allow_sas and not (control and method == 'GET' and path == '/pairings')):
            return failure(404, 'bridgeproxy_route_not_allowed', 'Core 业务接口不存在')
        if self._closed:
            return failure(503, 'bridgeproxy_closed', 'Core 适配器已经关闭')
        if self._reason:
            code = 'bridgeproxy_unconfigured' if self._reason == 'not_configured' else 'bridgeproxy_configuration_invalid'
            return failure(503, code, '尚未正确配置服务端本机 Core 和只读凭据')
        needs_control = control or method != 'GET'
        if needs_control and self._control_reason:
            return failure(503, 'bridgeproxy_control_unconfigured', '尚未配置服务端 Core 控制凭据')
        if len(body) > MAX_REQUEST_BYTES:
            return failure(413, 'body_too_large', '请求体超过 1 MiB')
        if method == 'GET' and body:
            return failure(400, 'unexpected_body', '读取接口不接受请求体')
        for value, limit in ((if_match, 256), (idempotency_key, 128)):
            if value is not None and (not value or len(value) > limit or
                                      any(ord(char) < 33 or ord(char) > 126 for char in value)):
                return failure(400, 'invalid_core_header', '配置版本或幂等键格式无效')
        try:
            secret_values = _request_secrets(_strict_json(body)) if body else []
        except (ValueError, RecursionError, UnicodeError):
            return failure(400, 'invalid_json', '请求体必须是有效的 UTF-8 JSON')
        token = self._control if needs_control else self._read
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json',
                   'Accept-Encoding': 'identity', 'Connection': 'close'}
        if body:
            headers['Content-Type'] = 'application/json'
        if if_match is not None:
            headers['If-Match'] = if_match
        if idempotency_key is not None:
            headers['Idempotency-Key'] = idempotency_key
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=1)
        except TimeoutError:
            return failure(429, 'bridgeproxy_busy', 'Core 适配器请求并发已满')
        try:
            if authorize is not None:
                authorize()
            async with asyncio.timeout(REQUEST_DEADLINE_SECONDS):
                async with self._client.stream(method, self.endpoint + '/v1' + path,
                                               headers=headers, content=body) as response:
                    if 300 <= response.status_code < 400:
                        return failure(502, 'bridgeproxy_redirect_rejected', 'Core 不应返回重定向')
                    if (response.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json'
                            or response.headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}):
                        return failure(502, 'bridgeproxy_invalid_response', 'Core 响应格式无效')
                    try:
                        declared = int(response.headers.get('content-length', '0'))
                    except ValueError:
                        return failure(502, 'bridgeproxy_invalid_response', 'Core 响应长度无效')
                    if declared < 0 or declared > MAX_RESPONSE_BYTES:
                        return failure(502, 'bridgeproxy_response_too_large', 'Core 响应超过边界')
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                            return failure(502, 'bridgeproxy_response_too_large', 'Core 响应超过边界')
                        raw.extend(chunk)
                    payload = _strict_json(bytes(raw))
                    if (not isinstance(payload, dict) or payload.get('api_version') != 'v1'
                            or ('data' in payload) == ('error' in payload)
                            or set(payload) - {'api_version', 'data', 'error'}
                            or ('error' in payload) != (response.status_code >= 400)):
                        return failure(502, 'bridgeproxy_invalid_response', 'Core 未返回有效的 v1 响应')
                    if 'error' in payload:
                        error = payload['error']
                        if (not isinstance(error, dict) or type(error.get('status')) is not int
                                or error['status'] != response.status_code
                                or not isinstance(error.get('code'), str) or not error['code']
                                or not isinstance(error.get('message'), str)):
                            return failure(502, 'bridgeproxy_invalid_response', 'Core 错误响应格式无效')
                    redacted = _redact(payload, (self._read, self._control, *secret_values), allow_sas,
                                       schema=path == '/openapi.json')
                    safe_headers = {}
                    etag = response.headers.get('etag')
                    if (etag and re.fullmatch(r'"[0-9a-fA-F]{64}"', etag)
                            and etag[1:-1] not in {self._read, self._control}):
                        safe_headers['ETag'] = etag
                    if authorize is not None:
                        authorize()
                    return CoreResponse(response.status_code, redacted, safe_headers)
        except (httpx.TimeoutException, TimeoutError):
            return failure(504, 'bridgeproxy_timeout', 'Core 请求超时；写操作结果未知，请查询状态，不要自动重试')
        except httpx.RequestError:
            return failure(503, 'bridgeproxy_unavailable', '无法连接服务端本机 Core，请检查进程与控制 API')
        except (ValueError, RecursionError, UnicodeError):
            return failure(502, 'bridgeproxy_invalid_response', 'Core 响应不是有效的有界 JSON')
        finally:
            self._slots.release()
