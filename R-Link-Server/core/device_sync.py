"""Application-owned NetBird inventory synchronization and lifecycle operations."""
import asyncio
from contextlib import suppress
from datetime import datetime
import ipaddress
import json
import logging
import sqlite3

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.concurrency import run_in_threadpool
from core import devices
from core.mesh import ID_RE, netbird, safe_id

logger = logging.getLogger(__name__)


async def run_database(function, *args, on_success=None):
    """Keep the owning operation alive until its database thread really stops.

    Cancelling a coroutine awaiting a threadpool does not stop the thread.
    Shield the worker and drain it before propagating cancellation, so callers
    retain their operation lock and lifecycle shutdown retains the service lock.
    """
    worker = asyncio.create_task(run_in_threadpool(function, *args))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(worker)
            break
        except asyncio.CancelledError:
            if worker.cancelled():
                raise
            cancelled = True
            if worker.done():
                try:
                    result = worker.result()
                except Exception:
                    raise asyncio.CancelledError from None
                break
        except Exception:
            if cancelled:
                raise asyncio.CancelledError from None
            raise
    # A cancelled request may have completed a durable mutation; record its
    # audit before propagating cancellation or releasing the operation lock.
    if on_success:
        on_success(result)
    if cancelled:
        raise asyncio.CancelledError
    return result


class PeerGroup(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)

    @field_validator('id')
    @classmethod
    def identifier(cls, value):
        if not ID_RE.fullmatch(value):
            raise ValueError('Invalid group identity')
        return value


class PeerObservation(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    ip: str
    connected: bool = Field(strict=True)
    os: str = Field(default='', max_length=200)
    last_seen: str | None = Field(default=None, max_length=80)
    groups: list[PeerGroup] = Field(default_factory=list, max_length=256)

    @field_validator('id')
    @classmethod
    def identifier(cls, value):
        if not ID_RE.fullmatch(value):
            raise ValueError('Invalid peer identity')
        return value

    @field_validator('ip')
    @classmethod
    def address(cls, value):
        address = ipaddress.ip_address(value)
        return devices.DeviceInput.normalize_host(str(address))

    @field_validator('last_seen')
    @classmethod
    def timestamp(cls, value):
        if value is not None:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError('An observation timestamp must contain a timezone')
            return parsed.isoformat()
        return None

    def platform(self):
        value = self.os.lower()
        for marker, platform in [('android', 'android'), ('ios', 'ios'), ('darwin', 'macos'), ('macos', 'macos'), ('mac os', 'macos'), ('windows', 'windows'), ('linux', 'linux')]:
            if marker in value:
                return platform
        return 'other' if value else 'unknown'


def validate_peers(payload):
    try:
        if not isinstance(payload, list):
            raise ValueError()
        result = [PeerObservation.model_validate(row) for row in payload]
        if len({row.id for row in result}) != len(result):
            raise ValueError()
        return result
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(502, 'NetBird 节点响应无效，未写入设备') from None


def health(db, provider, stamp=None, error=None):
    db.execute('''INSERT INTO device_sync_health(id,provider,last_synced_at,last_error) VALUES(1,?,?,?)
        ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,
        last_synced_at=CASE WHEN device_sync_health.provider=excluded.provider AND excluded.last_synced_at IS NULL
            THEN device_sync_health.last_synced_at ELSE excluded.last_synced_at END,last_error=excluded.last_error''',
        (provider, stamp, error))


def update_peer(db, row, peer, provider, stamp, linked=False):
    assignments = {'source': 'netbird', 'provider': provider, 'peer_id': peer.id,
                   'connection_status': 'online' if peer.connected else 'offline', 'last_seen': peer.last_seen,
                   'synced_at': stamp, 'mesh_groups': json.dumps([group.model_dump() for group in peer.groups])}
    if not row['name_override'] and not linked:
        assignments['name'] = peer.name
    if not row['platform_override']:
        assignments['platform'] = peer.platform()
    if linked:
        assignments['name_override'] = 1
    if row['host'] != peer.ip:
        assignments.update(host=peer.ip, revision=row['revision'] + 1, status='unchecked', checked_at=None, latency_ms=None)
    db.execute('UPDATE devices SET ' + ','.join(key + '=?' for key in assignments) + ' WHERE id=?', (*assignments.values(), row['id']))


def apply_sync(peers, provider):
    stamp = devices.now()
    summary = {'added': 0, 'updated': 0, 'missing': 0, 'conflicts': [], 'synced_at': stamp}
    with devices.database() as db:
        db.execute('BEGIN IMMEDIATE')
        excluded = {row['peer_id'] for row in db.execute('SELECT peer_id FROM device_exclusions WHERE provider=?', (provider,))}
        seen = {peer.id for peer in peers}
        for peer in peers:
            if peer.id in excluded:
                continue
            row = db.execute('SELECT * FROM devices WHERE provider=? AND peer_id=?', (provider, peer.id)).fetchone()
            endpoint = db.execute('SELECT * FROM devices WHERE host=? AND port=?', (peer.ip, row['port'] if row else 22)).fetchone()
            if endpoint and (not row or endpoint['id'] != row['id']):
                summary['conflicts'].append({'peer_id': peer.id, 'device_id': endpoint['id'], 'host': peer.ip,
                                            'port': endpoint['port'], 'reason': 'endpoint_already_registered'})
                if row:
                    # A conflicting new address cannot replace either row, but
                    # the old address and successful TCP check are now obsolete.
                    db.execute("""UPDATE devices SET connection_status='unknown',
                        synced_at=?,revision=revision+1,status='unchecked',
                        checked_at=NULL,latency_ms=NULL WHERE id=?""", (stamp, row['id']))
                continue
            if row:
                update_peer(db, dict(row), peer, provider, stamp)
                summary['updated'] += 1
            else:
                device_id = devices.insert_device(db, devices.DeviceInput(name=peer.name, host=peer.ip, platform=peer.platform(), access_mode='none'))
                db.execute('UPDATE devices SET platform_override=0 WHERE id=?', (device_id,))
                update_peer(db, devices.raw_device(db, device_id), peer, provider, stamp)
                summary['added'] += 1
        for row in db.execute('SELECT id,peer_id,connection_status FROM devices WHERE provider=? AND source=?', (provider, 'netbird')).fetchall():
            if row['peer_id'] not in seen and row['connection_status'] != 'revoked':
                db.execute("UPDATE devices SET connection_status='removed',synced_at=? WHERE id=?", (stamp, row['id']))
                summary['missing'] += 1
        health(db, provider, stamp)
    return summary


def mark_failed(provider):
    with devices.database() as db:
        db.execute("UPDATE devices SET connection_status='unknown' WHERE provider=? AND source='netbird' AND connection_status!='revoked'", (provider,))
        health(db, provider, error='设备同步失败，请检查 NetBird 管理连接和服务端配置')


def apply_link(device_id, peer, provider):
    try:
        with devices.database() as db:
            db.execute('BEGIN IMMEDIATE')
            row = devices.raw_device(db, device_id)
            existing = db.execute('SELECT id FROM devices WHERE provider=? AND peer_id=?', (provider, peer.id)).fetchone()
            if existing and existing['id'] != device_id:
                raise HTTPException(409, '该 NetBird 节点已关联另一台设备，请先处理现有关联')
            if row['gateway_id'] or (row['source'] == 'netbird' and (row['provider'] != provider or row['peer_id'] != peer.id)):
                raise HTTPException(409, '只有手动设备或当前相同节点可以关联')
            stamp = devices.now()
            update_peer(db, row, peer, provider, stamp, linked=True)
            db.execute('DELETE FROM device_exclusions WHERE provider=? AND peer_id=?', (provider, peer.id))
            # A successful explicit observation clears an old provider failure.
            health(db, provider, stamp)
            return devices.get_device(db, device_id)
    except sqlite3.IntegrityError:
        raise HTTPException(409, '该节点的地址和端口已登记在另一台设备上') from None


def mark_revoked(device_id, provider):
    with devices.database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = devices.raw_device(db, device_id)
        db.execute('INSERT OR IGNORE INTO device_exclusions(provider,peer_id) VALUES(?,?)', (provider, row['peer_id']))
        db.execute("UPDATE devices SET connection_status='revoked',synced_at=? WHERE id=?", (devices.now(), device_id))
        return devices.get_device(db, device_id)


class DeviceSync:
    def __init__(self, audit_state=None):
        self.lock = asyncio.Lock()
        self.interval = devices.integer_setting('R_LINK_DEVICE_SYNC_INTERVAL', 60)
        self.task = None
        self.syncing = False
        self.audit_state = audit_state

    def audit(self, action, resource):
        if self.audit_state is not None:
            self.audit_state.audit('devices.' + action, resource)

    def status(self):
        provider = devices.current_provider()
        with devices.database() as db:
            row = db.execute('SELECT * FROM device_sync_health WHERE id=1 AND provider=?', (provider,)).fetchone() if provider else None
        return {'configured': provider is not None, 'syncing': self.syncing, 'interval_seconds': self.interval,
                'stale_seconds': devices.integer_setting('R_LINK_DEVICE_STALE_SECONDS', 180, 1),
                'last_synced_at': row['last_synced_at'] if row else None, 'last_error': row['last_error'] if row else None}

    async def sync(self):
        async with self.lock:
            provider = devices.current_provider()
            if not provider:
                raise HTTPException(503, '请设置 R_LINK_NETBIRD_URL 和 R_LINK_NETBIRD_TOKEN')
            self.syncing = True
            try:
                payload = await netbird.request('GET', '/api/peers')
                peers = validate_peers(payload)
                result = await run_database(apply_sync, peers, provider,
                                            on_success=lambda result: self.audit('sync', 'inventory'))
                return result
            except HTTPException:
                await run_database(mark_failed, provider)
                self.audit('sync.failed', 'inventory')
                raise
            except Exception:
                await run_database(mark_failed, provider)
                self.audit('sync.failed', 'inventory')
                raise HTTPException(502, '设备同步失败，请检查 NetBird 管理连接') from None
            finally:
                self.syncing = False

    async def link(self, device_id, peer_id):
        async with self.lock:
            provider = devices.current_provider()
            if not provider:
                raise HTTPException(503, '请先配置 NetBird 管理连接')
            peer_id = safe_id(peer_id)
            payload = await netbird.request('GET', '/api/peers/' + peer_id)
            peers = validate_peers([payload])
            if peers[0].id != peer_id:
                raise HTTPException(502, 'NetBird 节点响应编号不匹配')
            result = await run_database(apply_link, device_id, peers[0], provider,
                                        on_success=lambda result: self.audit('link', device_id))
            return result

    async def revoke(self, device_id):
        async with self.lock:
            with devices.database() as db:
                row = devices.raw_device(db, device_id)
            provider = devices.current_provider()
            if not provider or row['source'] != 'netbird' or row['provider'] != provider or not row['peer_id']:
                raise HTTPException(409, '只有当前 NetBird 管理连接的直接节点可撤销接入')
            if row['connection_status'] == 'revoked':
                return devices.read_device(device_id)
            try:
                await netbird.request('DELETE', '/api/peers/' + safe_id(row['peer_id']))
            except HTTPException as exc:
                # The current binding was verified locally before DELETE. A 404
                # means that peer already has no network membership to revoke;
                # only this absence is idempotent success, never other errors.
                if exc.status_code != 404:
                    raise
            result = await run_database(mark_revoked, device_id, provider,
                                        on_success=lambda result: self.audit('revoke', device_id))
            return result

    async def start(self):
        if self.interval:
            self.task = asyncio.create_task(self._run(), name='device-sync')

    async def _run(self):
        while True:
            if devices.current_provider():
                try:
                    await self.sync()
                except HTTPException:
                    logger.warning('NetBird device synchronization failed')
                except Exception:
                    # Background failures must not kill lifecycle cleanup or leak upstream data.
                    await run_database(mark_failed, devices.current_provider())
                    logger.warning('Unexpected device synchronization failure')
            await asyncio.sleep(self.interval)

    async def close(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        # Manual API operations can still own a database worker even when no
        # background task is scheduled. Drain their operation lock as well.
        async with self.lock:
            pass


def onboarding():
    provider = devices.current_provider()
    platforms = [{'id': identifier, 'name': name, 'url': 'https://docs.netbird.io/get-started/install/' + identifier}
                 for identifier, name in [('windows', 'Windows'), ('linux', 'Linux'), ('macos', 'macOS'), ('android', 'Android'), ('ios', 'iOS')]]
    return {'configured': provider is not None, 'management_url': provider, 'platforms': platforms,
            'instructions': ['在云端或 NetBird Cloud 准备管理服务，在 R-Link 服务端配置管理地址和访问令牌。',
                             '在支持的平台安装 NetBird，通过相同管理服务登录或使用入网密钥接入，然后同步设备。',
                             '不支持客户端的路由器或 IoT 需要真实的 NetBird 网关及网络路由配置，再登记网关后的设备。',
                             '网关在线仅代表网关状态；SSH 和 Web 访问需要在设备上启用对应服务并配置访问策略。']}
