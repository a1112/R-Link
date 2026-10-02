"""Persistent inventory; TCP checks and mesh observations are independent."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import ipaddress
import json
import os
import re
import sqlite3
import threading
import uuid
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from core.paths import CONFIG_DIR

DB_LOCK = threading.RLock()
METADATA = ('device_type', 'platform', 'tags', 'notes', 'access_mode', 'web_scheme')
PORTABLE = ('name', 'host', 'port', 'username', *METADATA)
COLUMNS = {
    'device_type': "TEXT NOT NULL DEFAULT 'other'", 'platform': "TEXT NOT NULL DEFAULT 'unknown'",
    'tags': "TEXT NOT NULL DEFAULT '[]'", 'notes': "TEXT NOT NULL DEFAULT ''",
    'access_mode': "TEXT NOT NULL DEFAULT 'ssh'", 'web_scheme': "TEXT NOT NULL DEFAULT 'http'",
    'gateway_id': 'TEXT', 'source': "TEXT NOT NULL DEFAULT 'manual'", 'provider': 'TEXT',
    'peer_id': 'TEXT', 'connection_status': "TEXT NOT NULL DEFAULT 'unknown'", 'last_seen': 'TEXT',
    'synced_at': 'TEXT', 'mesh_groups': "TEXT NOT NULL DEFAULT '[]'",
    'name_override': 'INTEGER NOT NULL DEFAULT 0', 'platform_override': 'INTEGER NOT NULL DEFAULT 0',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def integer_setting(name, default, minimum=0):
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def current_provider():
    # Validate credentials and URL with the shared adapter; never retain its PAT.
    from core.mesh import configuration
    try:
        url, _ = configuration()
    except HTTPException:
        return None
    parsed = urlsplit(url)
    hostname = parsed.hostname.lower()
    if ':' in hostname:
        hostname = '[' + hostname + ']'
    port = parsed.port
    if port and port != (443 if parsed.scheme.lower() == 'https' else 80):
        hostname += ':' + str(port)
    return urlunsplit((parsed.scheme.lower(), hostname, '', '', ''))


class DeviceInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=22, ge=1, le=65535, strict=True)
    username: str = Field(default='', max_length=80)
    device_type: Literal['computer', 'server', 'nas', 'mobile', 'router', 'iot', 'other'] = 'other'
    platform: Literal['unknown', 'windows', 'linux', 'macos', 'android', 'ios', 'other'] = 'unknown'
    tags: list[str] = Field(default_factory=list, max_length=16)
    notes: str = Field(default='', max_length=500)
    access_mode: Literal['ssh', 'web', 'none'] = 'ssh'
    web_scheme: Literal['http', 'https'] = 'http'
    gateway_id: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator('tags')
    @classmethod
    def normalize_tags(cls, values):
        result = []
        for value in values:
            value = value.strip()
            if not value or len(value) > 32:
                raise ValueError('Tags must contain 1–32 characters')
            if value not in result:
                result.append(value)
        return result

    @field_validator('host')
    @classmethod
    def normalize_host(cls, value):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            host = value.rstrip('.').lower()
            if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or any(
                not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in host.split('.')
            ):
                raise ValueError('Use an IP address or hostname, without a URL or port')
            return host
        if address.is_unspecified or address.is_multicast or str(address) == '255.255.255.255' or '%' in value:
            raise ValueError('Use a unicast device address')
        return str(address)


class PortableDevice(DeviceInput):
    @model_validator(mode='before')
    @classmethod
    def no_gateway_identity(cls, value):
        if isinstance(value, dict) and 'gateway_id' in value:
            raise ValueError('Gateway identity is not portable')
        return value


class DeviceInventory(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1, 2] = 1
    devices: list[PortableDevice] = Field(max_length=256)


@contextmanager
def database():
    path = Path(os.getenv('R_LINK_DEVICES_DB', str(CONFIG_DIR / 'devices.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        db = sqlite3.connect(path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            # A single transaction covers all schema changes, including legacy rows.
            with db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("""CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, host TEXT NOT NULL, port INTEGER NOT NULL,
                    username TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'unchecked', checked_at TEXT, latency_ms REAL,
                    UNIQUE(host, port))""")
                present = {row['name'] for row in db.execute('PRAGMA table_info(devices)')}
                for name, definition in COLUMNS.items():
                    if name not in present:
                        db.execute(f'ALTER TABLE devices ADD COLUMN {name} {definition}')
                db.execute('CREATE UNIQUE INDEX IF NOT EXISTS device_peer_identity ON devices(provider,peer_id) WHERE peer_id IS NOT NULL')
                db.execute('CREATE TABLE IF NOT EXISTS device_exclusions (provider TEXT NOT NULL,peer_id TEXT NOT NULL,PRIMARY KEY(provider,peer_id))')
                db.execute('CREATE TABLE IF NOT EXISTS device_sync_health (id INTEGER PRIMARY KEY CHECK(id=1),provider TEXT,last_synced_at TEXT,last_error TEXT)')
            with db:
                yield db
        finally:
            db.close()


def raw_device(db, device_id):
    row = db.execute('SELECT * FROM devices WHERE id=?', (device_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Device not found')
    return dict(row)


def observation_status(db, row):
    if row['source'] != 'netbird' or row['provider'] != current_provider():
        return 'unknown'
    if row['connection_status'] == 'revoked':
        return 'revoked'
    health = db.execute('SELECT * FROM device_sync_health WHERE id=1').fetchone()
    if not health or health['provider'] != row['provider'] or health['last_error'] or not row['synced_at']:
        return 'unknown'
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(row['synced_at'])).total_seconds()
        if age > integer_setting('R_LINK_DEVICE_STALE_SECONDS', 180, 1):
            return 'unknown'
    except (ValueError, TypeError):
        return 'unknown'
    return row['connection_status']


def public_device(db, row):
    item = {key: value for key, value in row.items() if key not in ('provider', 'name_override', 'platform_override')}
    item['tags'] = json.loads(item['tags'])
    item['mesh_groups'] = json.loads(item['mesh_groups'])
    item['connection_status'] = observation_status(db, row)
    item['gateway_status'] = None
    if item['gateway_id']:
        gateway = db.execute('SELECT * FROM devices WHERE id=?', (item['gateway_id'],)).fetchone()
        item['gateway_status'] = observation_status(db, dict(gateway)) if gateway else 'unknown'
    return item


def get_device(db, device_id):
    return public_device(db, raw_device(db, device_id))


def read_device(device_id):
    with database() as db:
        return get_device(db, device_id)


def list_devices():
    with database() as db:
        return [public_device(db, dict(row)) for row in db.execute('SELECT * FROM devices ORDER BY name,id')]


def validate_gateway(db, gateway_id, device_id=None):
    if not gateway_id:
        return
    if gateway_id == device_id:
        raise HTTPException(409, 'A device cannot be its own gateway')
    gateway = db.execute('SELECT * FROM devices WHERE id=?', (gateway_id,)).fetchone()
    if (not gateway or gateway['source'] != 'netbird' or gateway['gateway_id'] or
            gateway['provider'] != current_provider() or gateway['connection_status'] == 'revoked'):
        raise HTTPException(409, 'Gateway must be an existing, unrevoked direct NetBird device')


def insert_device(db, data, device_id=None):
    if db.execute('SELECT COUNT(*) FROM devices').fetchone()[0] >= 256:
        raise HTTPException(409, 'Device limit reached (256)')
    validate_gateway(db, data.gateway_id, device_id)
    device_id = device_id or str(uuid.uuid4())
    values = data.model_dump()
    values['tags'] = json.dumps(values['tags'])
    values['id'] = device_id
    values['source'] = 'gateway' if data.gateway_id else 'manual'
    values['platform_override'] = int('platform' in data.model_fields_set)
    names = ','.join(values)
    placeholders = ','.join('?' for _ in values)
    db.execute(f'INSERT INTO devices ({names}) VALUES ({placeholders})', tuple(values.values()))
    return device_id


def save_device(data: DeviceInput, device_id=None):
    try:
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            if device_id:
                existing = raw_device(db, device_id)
                if existing['source'] == 'netbird' and data.host != existing['host']:
                    raise HTTPException(409, 'NetBird 直接节点地址由管理服务同步，请在上游修改节点地址')
                values = data.model_dump()
                for key in (*METADATA, 'gateway_id'):
                    if key not in data.model_fields_set:
                        values[key] = json.loads(existing[key]) if key == 'tags' else existing[key]
                validate_gateway(db, values['gateway_id'], device_id)
                if existing['source'] == 'netbird' and values['gateway_id']:
                    raise HTTPException(409, 'A direct NetBird device cannot be a gateway child')
                values['tags'] = json.dumps(values['tags'])
                values['source'] = existing['source'] if existing['source'] == 'netbird' else ('gateway' if values['gateway_id'] else 'manual')
                values['name_override'] = 1
                if 'platform' in data.model_fields_set:
                    values['platform_override'] = 1
                assignments = ','.join(key + '=?' for key in values)
                db.execute(f"UPDATE devices SET {assignments},revision=revision+1,status='unchecked',checked_at=NULL,latency_ms=NULL WHERE id=?", (*values.values(), device_id))
            else:
                device_id = insert_device(db, data)
            return get_device(db, device_id)
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'A device with this host and port already exists') from None


def delete_device(device_id):
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = raw_device(db, device_id)
        if row['peer_id']:
            db.execute('INSERT OR IGNORE INTO device_exclusions(provider,peer_id) VALUES (?,?)', (row['provider'], row['peer_id']))
        # Detach children atomically; deletion never leaves dangling gateway IDs.
        db.execute("UPDATE devices SET gateway_id=NULL,source='manual' WHERE gateway_id=?", (device_id,))
        db.execute('DELETE FROM devices WHERE id=?', (device_id,))


def export_inventory(version=1):
    if version not in (1, 2):
        raise HTTPException(422, 'Inventory version must be 1 or 2')
    keys = ('name', 'host', 'port', 'username') if version == 1 else PORTABLE
    return {'version': version, 'devices': [{key: row[key] for key in keys} for row in list_devices()]}


def import_inventory(inventory: DeviceInventory):
    try:
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            known = {(row['host'], row['port']) for row in db.execute('SELECT host,port FROM devices')}
            added = skipped = 0
            for item in inventory.devices:
                key = (item.host, item.port)
                if key in known:
                    skipped += 1
                    continue
                insert_device(db, item)
                known.add(key)
                added += 1
            return {'added': added, 'skipped': skipped}
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'A device with this host and port already exists') from None


def record_probe(device, reachable, latency_ms):
    with database() as db:
        db.execute("""UPDATE devices SET status=?,checked_at=?,latency_ms=?
            WHERE id=? AND revision=?""", ('reachable' if reachable else 'unreachable', now(),
            latency_ms if reachable else None, device['id'], device['revision']))
        return get_device(db, device['id'])
