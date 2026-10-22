"""R-Link device control and an opaque, authorized WireGuard frame relay.

Machine credentials are independent of browser sessions and service keys. This
module never accepts client private keys or decrypts WireGuard payloads.
"""
import asyncio
import base64
from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from typing import Literal
from urllib.parse import urlsplit
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from core.paths import CONFIG_DIR

DB_LOCK = threading.RLock()
HEARTBEAT_TTL = 45
DEFAULT_GROUP = 'rlink-devices'
MAX_PEERS = 255
MAX_FRAME = 4096
RELAY_QUEUE = 64
RELAY_RATE = 1000
RELAY_BYTES_RATE = 4 * 1024 * 1024


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def public_url():
    value = os.getenv('R_LINK_FABRIC_PUBLIC_URL') or os.getenv('R_LINK_PUBLIC_URL') or 'http://127.0.0.1:8210'
    parsed = urlsplit(value)
    if (any(ord(char) <= 32 or char == '\\' for char in value) or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}))):
        raise HTTPException(503, 'Fabric public URL must use HTTPS; HTTP is restricted to loopback')
    return value.rstrip('/')


def address_pool():
    try:
        network = ipaddress.ip_network(os.getenv('R_LINK_FABRIC_ADDRESS_POOL', '10.253.199.0/24'), strict=True)
        if network.version != 4 or network.num_addresses > 65536 or network.prefixlen > 30:
            raise ValueError()
        return network
    except ValueError:
        raise HTTPException(503, 'Fabric address pool must be an IPv4 /16 through /30 network') from None


def peer_uuid(value: str):
    try:
        parsed = uuid.UUID(value)
        if str(parsed) != value:
            raise ValueError()
        return value
    except (ValueError, AttributeError):
        raise HTTPException(400, 'Invalid fabric peer ID') from None


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Candidate(Input):
    ip: str = Field(min_length=1, max_length=64)
    port: int = Field(ge=1, le=65535, strict=True)

    @field_validator('ip')
    @classmethod
    def address(cls, value):
        address = ipaddress.ip_address(value)
        if ('%' in value or address.is_unspecified or address.is_multicast or address.is_loopback
                or address.is_link_local or str(address) == '255.255.255.255'):
            raise ValueError('Candidates must be unicast LAN or public addresses')
        return str(address)


class EnrollmentInput(Input):
    name: str = Field(min_length=1, max_length=80)
    groups: list[str] = Field(default_factory=lambda: [DEFAULT_GROUP], min_length=1, max_length=16)
    ttl_seconds: int = Field(default=3600, ge=300, le=86400, strict=True)
    uses: Literal[1] = 1


class Enroll(Input):
    enrollment_token: str = Field(min_length=20, max_length=256)
    name: str = Field(min_length=1, max_length=80)
    os: str = Field(default='', max_length=100)
    public_key: str
    udp_port: int = Field(default=0, ge=0, le=65535, strict=True)
    candidates: list[Candidate] = Field(default_factory=list, max_length=16)

    @field_validator('public_key')
    @classmethod
    def key(cls, value):
        try:
            decoded = base64.b64decode(value, validate=True)
        except ValueError:
            raise ValueError('WireGuard public key must be canonical base64 of 32 bytes') from None
        if len(decoded) != 32 or decoded == bytes(32) or base64.b64encode(decoded).decode() != value:
            raise ValueError('WireGuard public key must be canonical base64 of 32 nonzero bytes')
        return value


class PeerStatus(Input):
    peer_id: str
    path: Literal['direct', 'relay', 'none']
    last_handshake: int | None = Field(default=None, ge=0, strict=True)
    rtt_ms: float | None = Field(default=None, ge=0, le=60000, allow_inf_nan=False)

    @field_validator('peer_id')
    @classmethod
    def identifier(cls, value):
        return peer_uuid(value)


class Heartbeat(Input):
    candidates: list[Candidate] = Field(default_factory=list, max_length=16)
    tunnel_ready: bool = Field(default=False, strict=True)
    mode: Literal['vpn', 'transport-test'] = 'transport-test'
    peer_status: list[PeerStatus] = Field(default_factory=list, max_length=256)
    config_version: int | None = Field(default=None, ge=0, strict=True)


class PeerUpdate(Input):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    groups: list[str] | None = Field(default=None, min_length=1, max_length=16)


class GroupInput(Input):
    name: str = Field(min_length=1, max_length=80)
    peers: list[str] = Field(default_factory=list, max_length=256)


@contextmanager
def database():
    path = Path(os.getenv('R_LINK_FABRIC_DB', str(CONFIG_DIR / 'fabric.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        db = sqlite3.connect(path, timeout=10)
        os.chmod(path, 0o600)
        db.row_factory = sqlite3.Row
        try:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS fabric_meta (id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL);
                INSERT OR IGNORE INTO fabric_meta VALUES (1,1);
                CREATE TABLE IF NOT EXISTS fabric_groups (id TEXT PRIMARY KEY,name TEXT NOT NULL);
                INSERT OR IGNORE INTO fabric_groups VALUES ('rlink-devices','R-Link devices');
                CREATE TABLE IF NOT EXISTS fabric_enrollments (
                    id TEXT PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,name TEXT NOT NULL,
                    groups_json TEXT NOT NULL,expires_at INTEGER NOT NULL,uses INTEGER NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,revoked INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS fabric_peers (
                    id TEXT PRIMARY KEY,name TEXT NOT NULL,os TEXT NOT NULL,public_key TEXT UNIQUE NOT NULL,
                    virtual_ip TEXT UNIQUE NOT NULL,token_hash TEXT UNIQUE NOT NULL,groups_json TEXT NOT NULL,
                    candidates_json TEXT NOT NULL,udp_port INTEGER NOT NULL,created_at INTEGER NOT NULL,
                    last_seen INTEGER,tunnel_ready INTEGER NOT NULL DEFAULT 0,mode TEXT NOT NULL DEFAULT 'transport-test',
                    paths_json TEXT NOT NULL DEFAULT '[]',revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS fabric_pairs (
                    left_id TEXT NOT NULL,right_id TEXT NOT NULL,secret TEXT NOT NULL,
                    PRIMARY KEY(left_id,right_id));
                CREATE TABLE IF NOT EXISTS fabric_audit (
                    id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,created_at INTEGER NOT NULL);
            ''')
            with db:
                yield db
        finally:
            db.close()


def version(db):
    return db.execute('SELECT version FROM fabric_meta WHERE id=1').fetchone()[0]


def bump(db):
    db.execute('UPDATE fabric_meta SET version=version+1 WHERE id=1')
    return version(db)


def audit(db, actor, action, target):
    db.execute('INSERT INTO fabric_audit(actor,action,target,created_at) VALUES (?,?,?,?)',
               (actor, action, target, int(time.time())))


def valid_groups(db, groups):
    groups = list(dict.fromkeys(groups))
    if not groups or any(not db.execute('SELECT id FROM fabric_groups WHERE id=?', (group,)).fetchone() for group in groups):
        raise HTTPException(422, 'All enrollment groups must exist')
    return groups


def enrollment_metadata(row):
    return {'id': row['id'], 'name': row['name'], 'groups': json.loads(row['groups_json']),
            'expires_at': row['expires_at'], 'uses': row['uses'], 'used': row['used'],
            'revoked': bool(row['revoked']), 'created_at': row['created_at']}


def create_enrollment(data: EnrollmentInput, actor: str):
    token = secrets.token_urlsafe(48)
    current = int(time.time())
    identifier = str(uuid.uuid4())
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        groups = valid_groups(db, data.groups)
        db.execute('INSERT INTO fabric_enrollments(id,token_hash,name,groups_json,expires_at,uses,created_at) VALUES (?,?,?,?,?,?,?)',
                   (identifier, digest(token), data.name, json.dumps(groups), current + data.ttl_seconds, 1, current))
        audit(db, actor, 'enrollment.create', identifier)
        result = enrollment_metadata(db.execute('SELECT * FROM fabric_enrollments WHERE id=?', (identifier,)).fetchone())
        result['enrollment_token'] = token
        return result


def list_enrollments():
    with database() as db:
        return [enrollment_metadata(row) for row in db.execute('SELECT * FROM fabric_enrollments ORDER BY created_at,id')]


def revoke_enrollment(identifier, actor):
    with database() as db:
        changed = db.execute('UPDATE fabric_enrollments SET revoked=1 WHERE id=?', (identifier,))
        if changed.rowcount != 1:
            raise HTTPException(404, 'Enrollment not found')
        audit(db, actor, 'enrollment.revoke', identifier)
        return enrollment_metadata(db.execute('SELECT * FROM fabric_enrollments WHERE id=?', (identifier,)).fetchone())


def candidates_json(candidates):
    values = {(item.ip, item.port) for item in candidates}
    return json.dumps([{'ip': ip, 'port': port} for ip, port in sorted(values)], separators=(',', ':'))


def enroll(data: Enroll):
    current = int(time.time())
    token = secrets.token_urlsafe(48)
    identifier = str(uuid.uuid4())
    pool = address_pool()
    base = public_url()
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        enrollment = db.execute('SELECT * FROM fabric_enrollments WHERE token_hash=?', (digest(data.enrollment_token),)).fetchone()
        if (not enrollment or enrollment['revoked'] or enrollment['expires_at'] <= current or enrollment['used'] >= enrollment['uses']):
            raise HTTPException(401, 'Enrollment expired, used or revoked')
        if db.execute('SELECT COUNT(*) FROM fabric_peers').fetchone()[0] >= MAX_PEERS:
            raise HTTPException(409, 'Fabric peer limit reached')
        if db.execute('SELECT id FROM fabric_peers WHERE public_key=?', (data.public_key,)).fetchone():
            raise HTTPException(409, 'This device public key has already been enrolled')
        allocated = {row[0] for row in db.execute('SELECT virtual_ip FROM fabric_peers')}
        address = next((str(value) for value in pool.hosts() if str(value) not in allocated), None)
        if not address:
            raise HTTPException(409, 'Fabric address pool exhausted')
        groups = valid_groups(db, json.loads(enrollment['groups_json']))
        db.execute('INSERT INTO fabric_peers(id,name,os,public_key,virtual_ip,token_hash,groups_json,candidates_json,udp_port,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (identifier, data.name, data.os, data.public_key, address, digest(token), json.dumps(groups),
                    candidates_json(data.candidates), data.udp_port, current))
        db.execute('UPDATE fabric_enrollments SET used=used+1 WHERE id=?', (enrollment['id'],))
        revision = bump(db)
        audit(db, identifier, 'peer.enroll', identifier)
    return {'peer_id': identifier, 'device_token': token, 'virtual_ip': address, 'prefix_length': pool.prefixlen,
            'config_version': revision, 'config_url': base + '/api/fabric/agent/config', 'heartbeat_interval': 15}


def machine(token):
    if not isinstance(token, str) or not 20 <= len(token) <= 256:
        raise HTTPException(401, 'Valid fabric machine credential required')
    with database() as db:
        row = db.execute('SELECT * FROM fabric_peers WHERE token_hash=? AND revoked=0', (digest(token),)).fetchone()
        if not row:
            raise HTTPException(401, 'Valid fabric machine credential required')
        return dict(row)


def require_current(db, identifier):
    row = db.execute('SELECT * FROM fabric_peers WHERE id=? AND revoked=0', (identifier,)).fetchone()
    if not row:
        raise HTTPException(401, 'Fabric device revoked')
    return row


def machine_token_peer(identifier):
    with database() as db:
        row = db.execute('SELECT * FROM fabric_peers WHERE id=? AND revoked=0', (identifier,)).fetchone()
        return dict(row) if row else None


def peer_heartbeat_current(row):
    # Enrollment is allowed a short grace period to establish the first heartbeat.
    stamp = row['last_seen'] or row['created_at']
    return int(time.time()) - stamp < HEARTBEAT_TTL


def allowed(left, right):
    return (left['id'] != right['id'] and not left['revoked'] and not right['revoked']
            and bool(set(json.loads(left['groups_json'])) & set(json.loads(right['groups_json']))))


def allowed_pair(source, destination):
    with database() as db:
        left = db.execute('SELECT * FROM fabric_peers WHERE id=?', (source,)).fetchone()
        right = db.execute('SELECT * FROM fabric_peers WHERE id=?', (destination,)).fetchone()
        return bool(left and right and allowed(left, right))


def agent_config(identifier):
    base = public_url()
    pool = address_pool()
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        own = require_current(db, identifier)
        if ipaddress.ip_address(own['virtual_ip']) not in pool:
            raise HTTPException(503, 'Configured fabric pool does not contain this device address')
        peers = []
        for row in db.execute('SELECT * FROM fabric_peers WHERE revoked=0 ORDER BY id').fetchall():
            if not allowed(own, row):
                continue
            left, right = sorted((identifier, row['id']))
            pair = db.execute('SELECT secret FROM fabric_pairs WHERE left_id=? AND right_id=?', (left, right)).fetchone()
            secret = pair[0] if pair else base64.b64encode(secrets.token_bytes(32)).decode()
            if not pair:
                db.execute('INSERT INTO fabric_pairs VALUES (?,?,?)', (left, right, secret))
            peers.append({'peer_id': row['id'], 'public_key': row['public_key'], 'virtual_ip': row['virtual_ip'],
                          'candidates': json.loads(row['candidates_json']), 'pair_secret': secret,
                          'connected': bool(row['last_seen'] and int(time.time()) - row['last_seen'] < HEARTBEAT_TTL)})
        revision = version(db)
    return {'schema_version': 1, 'provider': 'rlink', 'peer_id': own['id'], 'public_key': own['public_key'],
            'virtual_ip': own['virtual_ip'], 'prefix_length': pool.prefixlen,
            'config_version': revision, 'config_ttl_seconds': HEARTBEAT_TTL, 'heartbeat_interval': 15,
            'stun_servers': [value.strip() for value in os.getenv('R_LINK_FABRIC_STUN_SERVERS', '').split(',') if value.strip()],
            'relay_url': ('wss://' if base.startswith('https://') else 'ws://') + base.split('://', 1)[1] + '/api/fabric/relay',
            'peers': peers}


def heartbeat(identifier, data: Heartbeat):
    current = int(time.time())
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        own = require_current(db, identifier)
        candidate_data = candidates_json(data.candidates)
        paths = []
        for observation in data.peer_status:
            target = db.execute('SELECT * FROM fabric_peers WHERE id=?', (observation.peer_id,)).fetchone()
            if not target or not allowed(own, target):
                raise HTTPException(403, 'Peer telemetry target is outside the device groups')
            if observation.last_handshake is not None and observation.last_handshake > current + 30:
                raise HTTPException(422, 'Handshake timestamp is in the future')
            paths.append(dict(observation.model_dump(), reported_at=current))
        if candidate_data != own['candidates_json']:
            bump(db)
        db.execute('UPDATE fabric_peers SET candidates_json=?,last_seen=?,tunnel_ready=?,mode=?,paths_json=? WHERE id=?',
                   (candidate_data, current, int(data.tunnel_ready), data.mode, json.dumps(paths), identifier))
        return {'config_version': version(db), 'server_time': current, 'expires_at': current + HEARTBEAT_TTL}


def public_peer(db, row):
    current = int(time.time())
    connected = bool(not row['revoked'] and row['last_seen'] and current - row['last_seen'] < HEARTBEAT_TTL)
    paths = []
    if connected:
        for observation in json.loads(row['paths_json']):
            target = db.execute('SELECT * FROM fabric_peers WHERE id=?', (observation['peer_id'],)).fetchone()
            if target and allowed(row, target):
                paths.append(observation)
    groups = [{'id': group, 'name': value['name']} for group in json.loads(row['groups_json'])
              if (value := db.execute('SELECT name FROM fabric_groups WHERE id=?', (group,)).fetchone())]
    confirmed = bool(connected and row['mode'] == 'vpn' and row['tunnel_ready'] and
                     any(path.get('last_handshake') and current - path['last_handshake'] < 180 for path in paths))
    return {'id': row['id'], 'peer_id': row['id'], 'name': row['name'], 'os': row['os'], 'ip': row['virtual_ip'],
            'virtual_ip': row['virtual_ip'], 'public_key': row['public_key'], 'groups': groups,
            'connected': connected, 'control_connected': connected, 'relay_connected': relay.connected(row['id']),
            'tunnel_ready_reported': bool(connected and row['tunnel_ready']), 'data_plane_confirmed': confirmed,
            'mode': row['mode'], 'paths': paths, 'revoked': bool(row['revoked']),
            'last_seen': row['last_seen'], 'created_at': row['created_at']}


def list_peers():
    with database() as db:
        return [public_peer(db, row) for row in db.execute('SELECT * FROM fabric_peers ORDER BY name,id').fetchall()]


def status():
    peers = list_peers()
    active = [peer for peer in peers if not peer['revoked']]
    actual_vpn = any(peer['mode'] == 'vpn' and peer['tunnel_ready_reported'] for peer in active)
    with database() as db:
        revision = version(db)
    return {'schema_version': 1, 'provider': 'rlink', 'control_url': public_url(), 'configured': True,
            'peers': len(active), 'connected': sum(peer['connected'] for peer in active), 'config_version': revision,
            'mode': 'direct+relay', 'mode_transport': 'vpn' if actual_vpn else ('transport-test' if any(peer['connected'] for peer in active) else 'unobserved'),
            'capabilities': {'enrollment': True, 'revocation': True, 'groups': True, 'p2p': True, 'relay': True,
                             'vpn': actual_vpn, 'policies': False, 'networks': False}}


def rotate_pairs(db, identifier):
    db.execute('DELETE FROM fabric_pairs WHERE left_id=? OR right_id=?', (identifier, identifier))


def revoke_peer(identifier, actor):
    peer_uuid(identifier)
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM fabric_peers WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, 'Fabric peer not found')
        db.execute("UPDATE fabric_peers SET revoked=1,tunnel_ready=0,paths_json='[]' WHERE id=?", (identifier,))
        rotate_pairs(db, identifier)
        bump(db)
        audit(db, actor, 'peer.revoke', identifier)
        return public_peer(db, db.execute('SELECT * FROM fabric_peers WHERE id=?', (identifier,)).fetchone())


def update_peer(identifier, data: PeerUpdate, actor):
    peer_uuid(identifier)
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = require_current(db, identifier)
        groups = valid_groups(db, data.groups) if data.groups is not None else json.loads(row['groups_json'])
        db.execute('UPDATE fabric_peers SET name=?,groups_json=? WHERE id=?',
                   (data.name or row['name'], json.dumps(groups), identifier))
        if set(groups) != set(json.loads(row['groups_json'])):
            rotate_pairs(db, identifier)
        bump(db)
        audit(db, actor, 'peer.update', identifier)
        return public_peer(db, db.execute('SELECT * FROM fabric_peers WHERE id=?', (identifier,)).fetchone())


def list_groups():
    with database() as db:
        peers = db.execute('SELECT id,groups_json FROM fabric_peers WHERE revoked=0').fetchall()
        return [{'id': row['id'], 'name': row['name'],
                 'peers': [peer['id'] for peer in peers if row['id'] in json.loads(peer['groups_json'])]}
                for row in db.execute('SELECT * FROM fabric_groups ORDER BY name,id')]


def save_group(data: GroupInput, actor, identifier=None):
    identifier = identifier or str(uuid.uuid4())
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        if any(not db.execute('SELECT id FROM fabric_peers WHERE id=? AND revoked=0', (value,)).fetchone() for value in data.peers):
            raise HTTPException(422, 'Group members must be active fabric peers')
        if not db.execute('SELECT id FROM fabric_groups WHERE id=?', (identifier,)).fetchone():
            db.execute('INSERT INTO fabric_groups VALUES (?,?)', (identifier, data.name))
        else:
            db.execute('UPDATE fabric_groups SET name=? WHERE id=?', (data.name, identifier))
        for row in db.execute('SELECT id,groups_json FROM fabric_peers WHERE revoked=0').fetchall():
            groups = set(json.loads(row['groups_json']))
            updated = (groups | {identifier}) if row['id'] in data.peers else (groups - {identifier})
            if groups != updated:
                db.execute('UPDATE fabric_peers SET groups_json=? WHERE id=?', (json.dumps(sorted(updated)), row['id']))
                rotate_pairs(db, row['id'])
        bump(db)
        audit(db, actor, 'group.save', identifier)
    return next(group for group in list_groups() if group['id'] == identifier)


class RelayConnection:
    def __init__(self, peer_id):
        self.peer_id = peer_id
        self.queue = asyncio.Queue(maxsize=RELAY_QUEUE)
        self.loop = asyncio.get_running_loop()

    def invalidate(self):
        def close():
            # A close signal takes priority over queued data.
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(None)
        if not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(close)
            except RuntimeError:
                pass


class Relay:
    def __init__(self):
        self.connections = {}
        self.rates = {}
        self.lock = threading.RLock()

    def connected(self, peer_id):
        with self.lock:
            current = self.connections.get(peer_id)
            if current and current.loop.is_closed():
                self.connections.pop(peer_id, None)
                return False
            return current is not None

    def rate_limit(self, peer_id):
        with self.lock:
            # Keep the same bucket across reconnects; enrolled peer count is bounded.
            return self.rates.setdefault(peer_id, RateLimit())

    def register(self, connection):
        with self.lock:
            previous = self.connections.get(connection.peer_id)
            if previous:
                previous.invalidate()
            self.connections[connection.peer_id] = connection

    def unregister(self, connection):
        with self.lock:
            if self.connections.get(connection.peer_id) is connection:
                self.connections.pop(connection.peer_id, None)

    def invalidate(self, peer_id):
        with self.lock:
            current = self.connections.get(peer_id)
            if current:
                current.invalidate()

    def invalidate_all(self):
        with self.lock:
            for connection in list(self.connections.values()):
                connection.invalidate()
                if connection.loop.is_closed():
                    self.connections.pop(connection.peer_id, None)

    def forward(self, connection, data):
        if not 17 <= len(data) <= MAX_FRAME:
            raise HTTPException(400, 'Relay frame length invalid')
        destination = str(uuid.UUID(bytes=data[:16]))
        if not allowed_pair(connection.peer_id, destination):
            raise HTTPException(403, 'Relay target outside device groups')
        with self.lock:
            if self.connections.get(connection.peer_id) is not connection:
                raise HTTPException(401, 'Relay connection replaced')
            target = self.connections.get(destination)
            if not target:
                return False
            # Replace the untrusted destination prefix with the actual authenticated source.
            frame = uuid.UUID(connection.peer_id).bytes + data[16:]
            if target.loop is not asyncio.get_running_loop():
                raise HTTPException(503, 'Relay requires a single ASGI worker/event loop')
            try:
                target.queue.put_nowait(frame)
            except asyncio.QueueFull:
                raise HTTPException(429, 'Relay destination queue full') from None
            return True


class RateLimit:
    def __init__(self):
        self.updated = time.monotonic()
        self.frames = RELAY_RATE * 2
        self.bytes = RELAY_BYTES_RATE * 2

    def allow(self, size):
        now = time.monotonic()
        elapsed = now - self.updated
        self.updated = now
        self.frames = min(RELAY_RATE * 2, self.frames + elapsed * RELAY_RATE)
        self.bytes = min(RELAY_BYTES_RATE * 2, self.bytes + elapsed * RELAY_BYTES_RATE)
        if self.frames < 1 or self.bytes < size:
            return False
        self.frames -= 1
        self.bytes -= size
        return True


relay = Relay()
