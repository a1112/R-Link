"""Persistent, bounded HTTP downloads with validated resume and public DNS pinning."""
import asyncio
import ipaddress
import os
from pathlib import Path
import re
import socket
import stat
import time
from urllib.parse import urljoin, urlsplit

import aiohttp
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from core.storage import validate_name, is_link


def allowed_hosts():
    return {host.strip().lower() for host in os.getenv('R_LINK_DOWNLOAD_ALLOWED_HOSTS', '').split(',') if host.strip()}


def public_address(address):
    value = ipaddress.ip_address(address)
    mapped = getattr(value, 'ipv4_mapped', None)
    return value.is_global and (mapped is None or mapped.is_global)


def validate_url(url):
    try:
        parts = urlsplit(url)
        port = parts.port
        host = parts.hostname
        if (parts.scheme not in ('http', 'https') or not host or parts.username or parts.password
                or parts.fragment or any(ord(c) < 33 for c in url) or '\\' in url):
            raise ValueError()
        if host.lower() not in allowed_hosts():
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                if not public_address(str(address)):
                    raise ValueError()
        if port == 0:
            raise ValueError()
    except ValueError:
        raise ValueError('仅允许无凭据的 HTTP/HTTPS 公网地址；内网地址需在服务端明确放行') from None
    return url


class PublicResolver(aiohttp.resolver.DefaultResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        records = await super().resolve(host, port, family)
        if host.lower() not in allowed_hosts() and any(not public_address(row['host']) for row in records):
            raise OSError('下载地址解析到了未放行的内网地址')
        return records


class DownloadInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    url: str = Field(min_length=1, max_length=4096)
    name: str = Field(min_length=1, max_length=160)

    @field_validator('url')
    @classmethod
    def check_url(cls, value):
        return validate_url(value)

    @field_validator('name')
    @classmethod
    def check_name(cls, value):
        try:
            return validate_name(value)
        except HTTPException as exc:
            raise ValueError(exc.detail) from None


class DownloadManager:
    def __init__(self, state):
        self.state = state
        self.directory = state.root / 'downloads'
        self.directory.mkdir(exist_ok=True, mode=0o700)
        self.tasks = {}
        self.lock = asyncio.Lock()
        self.slots = asyncio.Semaphore(3)
        self.max_bytes = int(os.getenv('R_LINK_DOWNLOAD_MAX_BYTES', str(512 * 1024 * 1024)))
        if self.max_bytes < 1:
            raise RuntimeError('R_LINK_DOWNLOAD_MAX_BYTES must be positive')

    def path(self, identifier, suffix='.part'):
        # IDs are never interpolated until looked up in the database.
        self.state.get('download', identifier)
        if not re.fullmatch(r'[a-f0-9-]{36}', identifier):
            raise HTTPException(400, '无效任务编号')
        path = self.directory / (identifier + suffix)
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if is_link(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise HTTPException(403, '下载文件不能为链接或特殊文件')
        return path

    def update(self, identifier, **changes):
        item = self.state.get('download', identifier)
        return self.state.save('download', dict(item, **changes), identifier)

    async def recover(self):
        for item in self.state.list('download'):
            if item['state'] in ('running', 'queued'):
                self.update(item['id'], state='queued', error=None)
                self.schedule(item['id'])

    def schedule(self, identifier):
        task = asyncio.create_task(self.run(identifier))
        self.tasks[identifier] = task
        task.add_done_callback(lambda done: self.tasks.pop(identifier, None) if self.tasks.get(identifier) is done else None)

    async def create(self, data):
        async with self.lock:
            if len(self.state.list('download')) >= 256:
                raise HTTPException(409, '下载任务已达 256 个，请先删除历史记录')
            item = self.state.save('download', dict(data.model_dump(), state='queued', downloaded=0,
                                                    total=None, validator=None, error=None))
            self.state.audit('download.create', item['id'])
            self.schedule(item['id'])
            return item

    async def action(self, identifier, action):
        async with self.lock:
            item = self.state.get('download', identifier)
            if action == 'resume':
                if item['state'] not in ('paused', 'failed', 'cancelled'):
                    raise HTTPException(409, '只有已暂停、失败或取消的任务可以继续')
                item = self.update(identifier, state='queued', error=None)
                self.schedule(identifier)
            elif action in ('pause', 'cancel', 'delete'):
                if action == 'pause' and item['state'] not in ('running', 'queued'):
                    raise HTTPException(409, '任务当前不可暂停')
                if action == 'cancel' and item['state'] == 'completed':
                    raise HTTPException(409, '已完成任务请使用删除操作')
                task = self.tasks.get(identifier)
                if task:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                part = self.path(identifier)
                size = part.stat().st_size if part.exists() else 0
                if action in ('cancel', 'delete'):
                    part.unlink(missing_ok=True)
                    size = 0
                if action == 'delete':
                    self.path(identifier, '.file').unlink(missing_ok=True)
                    self.state.delete('download', identifier)
                    item = None
                else:
                    item = self.update(identifier, state='paused' if action == 'pause' else 'cancelled', downloaded=size)
            else:
                raise HTTPException(400, '不支持此操作')
            self.state.audit('download.' + action, identifier)
            return item

    async def run(self, identifier):
        try:
            async with self.slots:
                self.update(identifier, state='running', error=None)
                # Connector resolves and checks the actual addresses used for connections,
                # preventing a second unchecked DNS lookup after a preflight check.
                connector = aiohttp.TCPConnector(resolver=PublicResolver(), limit=3)
                async with aiohttp.ClientSession(connector=connector, trust_env=False, auto_decompress=False,
                                                timeout=aiohttp.ClientTimeout(total=None, connect=15, sock_read=30)) as session:
                    await self.transfer(session, identifier)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if isinstance(exc, (ValueError, HTTPException)):
                message = str(exc.detail if isinstance(exc, HTTPException) else exc)
            else:
                # Do not reflect signed URLs or proxy credentials in network errors.
                message = '下载失败，请检查网络、文件大小和磁盘空间 (' + type(exc).__name__ + ')'
            self.update(identifier, state='failed', error=message[:300])

    async def transfer(self, session, identifier):
        item = self.state.get('download', identifier)
        part = self.path(identifier)
        destination = self.path(identifier, '.file')
        if destination.exists():
            # Atomic publish succeeded before the previous process committed the state.
            self.update(identifier, state='completed', downloaded=destination.stat().st_size,
                        total=destination.stat().st_size, error=None)
            return
        offset = part.stat().st_size if part.exists() and item.get('validator') else 0
        headers = {'Accept-Encoding': 'identity'}
        if offset:
            headers.update({'Range': f'bytes={offset}-', 'If-Range': item['validator']})
        url = item['url']
        for attempt in range(7):
            validate_url(url)
            async with session.get(url, headers=headers, allow_redirects=False) as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location')
                    if not location:
                        raise ValueError('重定向缺少目标地址')
                    next_url = urljoin(url, location)
                    if urlsplit(url).scheme == 'https' and urlsplit(next_url).scheme != 'https':
                        raise ValueError('拒绝 HTTPS 下载降级到 HTTP')
                    url = next_url
                    continue
                if response.status == 416 and offset:
                    offset = 0
                    headers = {'Accept-Encoding': 'identity'}
                    continue
                if response.status not in (200, 206):
                    raise ValueError(f'下载源返回 HTTP {response.status}')
                if response.headers.get('Content-Encoding', 'identity') != 'identity':
                    raise ValueError('下载源未遵守 identity 编码，无法安全续传')
                total = response.content_length
                etag = response.headers.get('ETag', '')
                validator = etag if etag and not etag.startswith('W/') else response.headers.get('Last-Modified')
                if response.status == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if not offset or not match or int(match[1]) != offset or int(match[2]) != int(match[3]) - 1:
                        raise ValueError('下载源返回无效续传范围')
                    if validator != item.get('validator'):
                        raise ValueError('远端文件已变化，续传被拒绝；请取消后重新开始')
                    total = int(match[3])
                else:
                    offset = 0
                if total is not None and total > self.max_bytes:
                    raise ValueError('文件超过服务端下载大小限制')
                self.update(identifier, downloaded=offset, total=total, validator=validator)
                last = time.monotonic()
                with part.open('ab' if offset else 'wb') as output:
                    async for block in response.content.iter_chunked(128 * 1024):
                        if offset + len(block) > self.max_bytes:
                            raise ValueError('文件超过服务端下载大小限制')
                        output.write(block)
                        offset += len(block)
                        if time.monotonic() - last > 0.5:
                            self.update(identifier, downloaded=offset)
                            last = time.monotonic()
                    output.flush()
                    os.fsync(output.fileno())
                if total is not None and offset != total:
                    raise ValueError('文件长度与下载源声明不一致')
                part.replace(destination)
                self.update(identifier, state='completed', downloaded=offset, total=offset, error=None)
                self.state.audit('download.complete', identifier)
                return
        raise ValueError('下载重定向次数过多')

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
