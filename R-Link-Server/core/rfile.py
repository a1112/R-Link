"""Bounded adapter over the existing R-File watch and bridge protocols."""
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import re
import secrets
import ssl
import tempfile
import threading
from urllib.parse import urlsplit
import uuid

import httpx
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from core.paths import SERVER_DIR
from core.device_sync import drain_task
from core.rfile_permissions import checked_identity_path, make_private

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
DEVICE_FIELDS = ('deviceId', 'deviceName', 'deviceType', 'platform', 'presence', 'connectivity',
                 'trustState', 'deviceRole', 'initiationStatus', 'initiationBlockedReason')


def observation(state, error=None):
    return {'state': state, 'error': error, 'checked_at': datetime.now(timezone.utc).isoformat()}


class TransferFile:
    """A response owns its spool and transfer slot until either cleanup closes it."""
    def __init__(self, file, release):
        self.file = file
        self.release = release
        self.loop = asyncio.get_running_loop()
        self.closed = False
        self.lock = threading.Lock()

    def read(self, size=-1):
        return self.file.read(size)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
        try:
            self.file.close()
        finally:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None
            if current_loop is self.loop:
                self.release()
            elif not self.loop.is_closed():
                self.loop.call_soon_threadsafe(self.release)


def service_url(value):
    url = urlsplit(value)
    if (url.scheme not in {'http', 'https'} or not url.hostname or url.username is not None
            or url.password is not None or url.query or url.fragment or any(ord(c) < 33 for c in value)):
        raise ValueError()
    url.port
    return value.rstrip('/')


def relative_parts(value, windows=False):
    if not isinstance(value, str) or len(value) > 1800 or any(ord(c) < 32 for c in value) or '\\' in value or ':' in value:
        raise HTTPException(400, '文件路径无效')
    if not value:
        return ()
    parts = value.split('/')
    if any(not part or part in {'.', '..'} or len(part) > 240 for part in parts):
        raise HTTPException(400, '文件路径无效')
    if windows and any(part.endswith((' ', '.')) or re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', part, re.I)
                       or any(c in part for c in '<>"|?*') for part in parts):
        raise HTTPException(400, '文件路径无效')
    return tuple(parts)


def controller_identity(directory):
    directory.mkdir(parents=True, exist_ok=True)
    checked_identity_path(directory, directory=True)
    target = directory / 'controller.json'
    try:
        checked_identity_path(target)
    except FileNotFoundError:
        exists = False
    else:
        exists = True
    make_private(directory, directory=True)
    if exists:
        make_private(target)
        if target.stat().st_size > 4096:
            raise ValueError()
        data = json.loads(target.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('id'), str) or len(data['id']) != 36:
            raise ValueError()
        uuid.UUID(data['id'])
        if not isinstance(data['key'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', data['key']):
            raise ValueError()
        return data
    data = {'id': str(uuid.uuid4()), 'key': secrets.token_urlsafe(48)}
    descriptor, name = tempfile.mkstemp(prefix='.controller-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            make_private(name)
            json.dump(data, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, target)
        make_private(target)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)
    return data


class RFile:
    def __init__(self, *, transport=None):
        self.watch_url = self.bridge_url = ''
        self.config_error = None
        self.root = None
        self.windows = False
        self.interval = 30.0
        self.identity = None
        self.registered = False
        self.registration_attempted = False
        self.closed = False
        self.worker = None
        self.operations = set()
        self.downloads = set()
        self.lock = asyncio.Lock()
        self.transfers = asyncio.Semaphore(4)
        self.watch = {'state': 'unchecked', 'error': None, 'checked_at': None}
        self.network = {'state': 'unchecked', 'error': None, 'checked_at': None}
        self.devices = []
        self.active_sessions = None
        self.headers = {}
        self.identity_dir = Path(os.getenv('R_LINK_DATA_DIR') or SERVER_DIR / 'data') / 'rfile'
        try:
            self.watch_url = service_url(os.getenv('R_LINK_RFILE_URL') or os.getenv('RFILE_SERVICE_URL') or 'http://127.0.0.1:18080')
            self.bridge_url = service_url(os.getenv('R_LINK_RFILE_BRIDGE_URL') or os.getenv('RFILE_BRIDGE_URL') or 'http://127.0.0.1:18100')
            self.interval = float(os.getenv('R_LINK_RFILE_INTERVAL', '30'))
            if not (self.interval == 0 or 1 <= self.interval <= 300):
                raise ValueError()
            context = ssl.create_default_context()
            if certificate := os.getenv('R_LINK_RFILE_CA_CERT'):
                context.load_verify_locations(cafile=certificate)
            root = os.getenv('R_LINK_RFILE_ROOT', '')
            if not root:
                roots = [item.strip() for item in os.getenv('RFILE_ALLOWED_ROOTS', '').split(';') if item.strip()]
                root = roots[0] if len(roots) == 1 else ''
            if root:
                self.windows = bool(re.match(r'^[A-Za-z]:', root) or root.startswith('\\\\'))
                self.root = (PureWindowsPath if self.windows else PurePosixPath)(root)
                if not self.root.is_absolute() or '..' in self.root.parts or any(ord(c) < 32 for c in root):
                    raise ValueError()
            session = os.getenv('R_LINK_RFILE_SESSION_TOKEN', '')
            admin = os.getenv('R_LINK_RFILE_TOKEN') or os.getenv('RFILE_SERVICE_ACCESS_TOKEN', '')
            if session or admin:
                credential = session or admin
                if len(credential) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in credential):
                    raise ValueError()
                self.headers = {'x-rfile-session-token' if session else 'x-rfile-service-token': credential}
        except (ValueError, OSError, TypeError):
            self.config_error = 'R-File 服务端配置无效，请检查地址、共享目录和受信任证书'
            self.watch_url = self.bridge_url = ''
            self.root = None
            self.headers = {}
            context = ssl.create_default_context()
        self.client = httpx.AsyncClient(transport=transport, verify=context, trust_env=False,
            headers={'Accept-Encoding': 'identity'},
            follow_redirects=False, timeout=httpx.Timeout(5, connect=2),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4))

    def status(self):
        enabled = bool(self.root and self.headers and not self.config_error)
        return {'watch': {'url': self.watch_url, **self.watch},
                'network': {'url': self.bridge_url, **self.network, 'controller_registered': self.registered,
                            'active_sessions': self.active_sessions},
                'files': {'enabled': enabled, 'max_file_bytes': MAX_FILE_BYTES,
                          'reason': None if enabled else '在服务端配置 R-File 访问凭据和一个共享目录后可浏览文件'},
                'devices': [dict(row) for row in self.devices], 'config_error': self.config_error}

    async def start(self):
        if self.interval and not self.config_error:
            self.worker = asyncio.create_task(self._loop())

    async def _loop(self):
        while True:
            try:
                await self.refresh()
            except HTTPException as exc:
                if exc.status_code != 429:
                    self.devices = []
                    self.network = observation('offline', 'R-File 网络服务暂时不可用')
            await asyncio.sleep(self.interval)

    @asynccontextmanager
    async def operation(self, *, transfer=False):
        if self.closed:
            raise HTTPException(503, 'R-File 服务正在关闭')
        if transfer and self.transfers.locked():
            raise HTTPException(429, '文件传输繁忙，请稍后再试')
        if transfer:
            await self.transfers.acquire()
        task = asyncio.current_task()
        self.operations.add(task)
        reservation = {'retained': False}
        try:
            async with asyncio.timeout(120 if transfer else 15):
                yield reservation
        except (httpx.HTTPError, TimeoutError, OSError):
            raise HTTPException(503, 'R-File 服务暂时不可用') from None
        finally:
            self.operations.discard(task)
            if transfer and not reservation['retained']:
                self.transfers.release()

    @staticmethod
    def check_response(response):
        if 200 <= response.status_code < 300:
            # httpx decompresses before chunking, so reject encodings before reading.
            if response.headers.get('content-encoding', '').strip().lower() not in {'', 'identity'}:
                raise HTTPException(502, 'R-File 压缩响应不受支持')
            return
        messages = {401: 'R-File 访问凭据无效', 403: 'R-File 拒绝访问该共享目录',
                    404: 'R-File 文件或服务不存在', 409: 'R-File 已存在同名文件', 413: '单文件不能超过 64 MiB'}
        raise HTTPException(response.status_code if response.status_code in messages else 502,
                            messages.get(response.status_code, 'R-File 服务响应无效'))

    async def request(self, method, base, endpoint, **kwargs):
        async with self.client.stream(method, base + endpoint, **kwargs) as response:
            self.check_response(response)
            if response.status_code == 204:
                return None
            body = bytearray()
            async for chunk in response.aiter_bytes(min(64 * 1024, MAX_JSON_BYTES + 1)):
                if len(body) + len(chunk) > MAX_JSON_BYTES:
                    raise HTTPException(502, 'R-File 服务响应过大')
                body.extend(chunk)
            try:
                return json.loads(body)
            except (ValueError, UnicodeError):
                raise HTTPException(502, 'R-File 服务响应无效') from None

    async def health(self, base, endpoint, expected):
        data = await self.request('GET', base, endpoint)
        if not isinstance(data, dict) or data.get('service') != expected or data.get('status') != 'ok':
            raise HTTPException(502, '服务身份与 R-File 不匹配')
        return data

    def device_headers(self):
        return {'x-rfile-device-id': self.identity['id'], 'x-rfile-device-token': self.identity['key']}

    async def refresh(self):
        try:
            return await self._refresh_once()
        except HTTPException as exc:
            if exc.status_code == 503:
                self.devices = []
                self.active_sessions = None
                self.registered = False
                self.network = observation('offline', 'R-File 网络服务暂时不可用')
            raise

    async def _refresh_once(self):
        if self.config_error or self.closed:
            return self.status()
        if self.lock.locked():
            raise HTTPException(429, 'R-File 状态正在刷新')
        async with self.lock, self.operation():
            self.devices = []
            self.active_sessions = None
            try:
                await self.health(self.watch_url, '/api/v1/health', 'rfile-watch')
                self.watch = observation('online')
            except (HTTPException, httpx.HTTPError, TimeoutError):
                self.watch = observation('offline', 'R-File 文件服务不可用或身份不匹配')
            try:
                bridge_health = await self.health(self.bridge_url, '/api/v1/bridge/health', 'rfile-bridge')
                active_sessions = bridge_health.get('activeSessions')
                if type(active_sessions) is not int or not 0 <= active_sessions < 2 ** 53:
                    raise HTTPException(502, 'R-File 会话状态响应无效')
                if self.identity is None:
                    try:
                        worker = asyncio.create_task(asyncio.to_thread(controller_identity, self.identity_dir))
                        self.identity = await drain_task(worker)
                    except (OSError, ValueError, KeyError, TypeError):
                        raise HTTPException(503, 'R-File 控制端身份无法保存') from None
                if not self.registered:
                    self.registration_attempted = True
                    await self.request('POST', self.bridge_url, '/api/v1/bridge/register', headers=self.device_headers(), json={
                        'deviceId': self.identity['id'], 'deviceName': 'R-Link · ' + platform.node()[:80],
                        'deviceType': 'remote', 'platform': platform.system().lower(), 'trustState': 'trusted',
                        'presence': 'online', 'connectivity': 'relay', 'apiUrl': 'http://127.0.0.1:18080',
                        'wsUrl': 'ws://127.0.0.1:18080/ws', 'accessToken': None, 'capabilities': [],
                        'accessPolicy': {'canInitiateRemoteSessions': True, 'canAcceptRemoteSessions': False,
                            'deviceVisibility': 'all', 'allowedTargetDeviceIds': [], 'allowedSourceDeviceIds': []}})
                    self.registered = True
                else:
                    await self.request('POST', self.bridge_url, '/api/v1/bridge/heartbeat', headers=self.device_headers(),
                                       json={'deviceId': self.identity['id']})
                peers = await self.request('GET', self.bridge_url, '/api/v1/bridge/devices', headers=self.device_headers())
                if not isinstance(peers, list) or len(peers) > 4096:
                    raise HTTPException(502, 'R-File 设备响应无效')
                devices = []
                identities = set()
                for row in peers:
                    if (not isinstance(row, dict) or not isinstance(row.get('deviceId'), str)
                            or not 1 <= len(row['deviceId']) <= 240 or row['deviceId'] in identities):
                        raise HTTPException(502, 'R-File 设备响应无效')
                    identities.add(row['deviceId'])
                    if row['deviceId'] == self.identity['id']:
                        continue
                    devices.append({field: row[field] for field in DEVICE_FIELDS
                                    if isinstance(row.get(field), str) and len(row[field]) <= 240})
                self.devices = devices
                self.active_sessions = active_sessions
                self.network = observation('online')
            except (HTTPException, httpx.HTTPError, TimeoutError):
                self.network = observation('offline', 'R-File 网络服务不可用或设备注册失败')
                self.registered = False
        return self.status()

    async def close(self):
        if self.closed:
            return
        self.closed = True
        tasks = [task for task in self.operations if task is not asyncio.current_task()]
        if self.worker and self.worker not in tasks:
            tasks.append(self.worker)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        try:
            if self.registration_attempted and self.identity:
                with suppress(HTTPException, httpx.HTTPError, TimeoutError):
                    async with asyncio.timeout(3):
                        await self.request('POST', self.bridge_url, '/api/v1/bridge/unregister',
                            headers=self.device_headers(), json={'deviceId': self.identity['id']})
        finally:
            self.registered = False
            self.registration_attempted = False
            self.active_sessions = None
            for file in list(self.downloads):
                file.close()
            await self.client.aclose()

    def file_path(self, relative):
        if self.config_error or not self.root or not self.headers:
            raise HTTPException(409, '请在服务端配置 R-File 访问凭据和共享目录')
        return self.root.joinpath(*relative_parts(relative, self.windows))

    def relative_path(self, absolute):
        if not isinstance(absolute, str):
            raise HTTPException(502, 'R-File 文件响应无效')
        path = (PureWindowsPath if self.windows else PurePosixPath)(absolute)
        if not path.is_absolute() or '..' in path.parts:
            raise HTTPException(403, 'R-File 返回了共享目录外的路径')
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            raise HTTPException(403, 'R-File 返回了共享目录外的路径') from None
        relative = '' if relative == '.' else relative
        relative_parts(relative, self.windows)
        return relative

    def normalize_entry(self, data):
        if not isinstance(data, dict) or data.get('kind') not in {'file', 'folder'}:
            raise HTTPException(403, '不允许访问链接或不支持的文件类型')
        if any(data.get(key) for key in ('symlinkTarget', 'aliasTarget', 'linkTargetPath', 'isAlias')):
            raise HTTPException(403, '不允许访问链接')
        relative = self.relative_path(data.get('path'))
        name = data.get('name')
        if not isinstance(name, str) or (relative and relative.split('/')[-1] != name):
            raise HTTPException(502, 'R-File 文件响应无效')
        size = data.get('size')
        if size is not None and (type(size) is not int or size < 0):
            raise HTTPException(502, 'R-File 文件大小无效')
        return {'path': relative, 'name': name, 'kind': 'directory' if data['kind'] == 'folder' else 'file',
                'size': size, 'modified_at': data.get('mtime') if isinstance(data.get('mtime'), str) else '',
                'readonly': data.get('readonly') is not False}

    async def checked_path(self, relative, kind):
        path = self.file_path(relative)
        if self.watch['state'] != 'online':
            await self.health(self.watch_url, '/api/v1/health', 'rfile-watch')
            self.watch = observation('online')
        parts = relative_parts(relative, self.windows)
        metadata = None
        for index in range(len(parts) + 1):
            current = self.root.joinpath(*parts[:index])
            data = await self.request('GET', self.watch_url, '/api/v1/stat', params={'path': str(current)}, headers=self.headers)
            metadata = self.normalize_entry(data)
            if metadata['path'] != '/'.join(parts[:index]):
                raise HTTPException(403, 'R-File 返回了不匹配的文件路径')
            expected = kind if index == len(parts) else 'directory'
            if metadata['kind'] != expected:
                raise HTTPException(400, 'R-File 文件类型不匹配')
        return path, metadata

    async def list_directory(self, relative):
        self.file_path(relative)
        async with self.operation():
            path, metadata = await self.checked_path(relative, 'directory')
            data = await self.request('GET', self.watch_url, '/api/v1/list', headers=self.headers, params={'path': str(path)})
            if (not isinstance(data, dict) or self.relative_path(data.get('path')) != relative
                    or not isinstance(data.get('entries'), list) or len(data['entries']) > 10000):
                raise HTTPException(502, 'R-File 目录响应无效')
            entries, skipped = [], 0
            for row in data['entries']:
                try:
                    item = self.normalize_entry(row)
                    parent = item['path'].rsplit('/', 1)[0] if '/' in item['path'] else ''
                    if parent != relative or not item['path']:
                        raise HTTPException(403, 'R-File 目录条目路径不匹配')
                    entries.append(item)
                except HTTPException:
                    skipped += 1
            return {'path': relative, 'entries': entries, 'skipped': skipped,
                    'max_file_bytes': MAX_FILE_BYTES, 'writable': not metadata['readonly']}

    async def upload(self, relative, name, file, size):
        self.validate_upload(relative, name, size)
        async with self.operation(transfer=True):
            return await self._upload(relative, name, file)

    def validate_upload(self, relative, name, size=0):
        self.file_path(relative)
        if len(relative_parts(name, self.windows)) != 1:
            raise HTTPException(400, '文件名无效')
        if size > MAX_FILE_BYTES:
            raise HTTPException(413, '单文件不能超过 64 MiB')

    async def upload_stream(self, relative, name, chunks):
        self.validate_upload(relative, name)
        async with self.operation(transfer=True):
            with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as file:
                size = 0
                async for chunk in chunks:
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise HTTPException(413, '单文件不能超过 64 MiB')
                    worker = asyncio.create_task(run_in_threadpool(file.write, chunk))
                    await drain_task(worker)
                file.seek(0)
                return await self._upload(relative, name, file)

    async def _upload(self, relative, name, file):
        path, metadata = await self.checked_path(relative, 'directory')
        if metadata['readonly']:
            raise HTTPException(403, 'R-File 目录为只读')
        data = await self.request('POST', self.watch_url, '/api/v1/upload', headers=self.headers,
            data={'path': str(path), 'conflictPolicy': 'reject'}, files={'file': (name, file, 'application/octet-stream')})
        result = self.normalize_entry(data)
        if result['path'] != '/'.join(filter(None, (relative, name))) or result['kind'] != 'file':
            raise HTTPException(502, 'R-File 上传响应无效')
        return result

    async def download(self, relative):
        self.file_path(relative)
        file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
        try:
            async with self.operation(transfer=True) as reservation:
                path, metadata = await self.checked_path(relative, 'file')
                if metadata['size'] is not None and metadata['size'] > MAX_FILE_BYTES:
                    raise HTTPException(413, '单文件不能超过 64 MiB')
                size = 0
                async with self.client.stream('GET', self.watch_url + '/api/v1/download',
                        params={'path': str(path)}, headers=self.headers) as response:
                    self.check_response(response)
                    async for chunk in response.aiter_bytes(64 * 1024):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            raise HTTPException(413, '单文件不能超过 64 MiB')
                        worker = asyncio.create_task(run_in_threadpool(file.write, chunk))
                        await drain_task(worker)
                file.seek(0)
                def release():
                    self.downloads.discard(owned)
                    self.transfers.release()
                owned = TransferFile(file, release)
                self.downloads.add(owned)
                reservation['retained'] = True
                return owned, metadata['name'], size
        except BaseException:
            file.close()
            raise
