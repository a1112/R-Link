"""Server-derived fabric projection into the existing shared device inventory.

The control plane and its telemetry remain authoritative. A heartbeat or assigned
address alone never makes a device's VPN connection online.
"""
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from core import devices, fabric


def provider():
    return fabric.public_url() + '#rlink-fabric'


def platform(value):
    value = value.lower()
    for needle, result in [('windows', 'windows'), ('darwin', 'macos'), ('mac', 'macos'),
                           ('linux', 'linux'), ('android', 'android'), ('ios', 'ios')]:
        if needle in value:
            return result
    return 'other' if value else 'unknown'


def connection_state(row):
    if row.get('provider') != provider() or not row.get('peer_id'):
        return 'unknown'
    peer = fabric.machine_token_peer(row['peer_id'])
    if peer is None:
        # Lookup revoked peers explicitly; machine authorization deliberately excludes them.
        with fabric.database() as db:
            raw = db.execute('SELECT revoked FROM fabric_peers WHERE id=?', (row['peer_id'],)).fetchone()
        return 'revoked' if raw and raw['revoked'] else 'unknown'
    with fabric.database() as db:
        public = fabric.public_peer(db, peer)
    return 'online' if public['data_plane_confirmed'] else 'unknown'


def project(peer_id):
    """Preserve device metadata and explicit exclusions; never auto-merge IP conflicts."""
    with fabric.database() as db:
        raw = db.execute('SELECT * FROM fabric_peers WHERE id=?', (peer_id,)).fetchone()
        if not raw:
            raise HTTPException(404, 'Fabric peer not found')
        peer = fabric.public_peer(db, raw)
    identity = provider()
    with devices.database() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT peer_id FROM device_exclusions WHERE provider=? AND peer_id=?', (identity, peer_id)).fetchone():
            return {'projected': False, 'reason': 'inventory_exclusion'}
        row = db.execute('SELECT * FROM devices WHERE provider=? AND peer_id=?', (identity, peer_id)).fetchone()
        endpoint = db.execute('SELECT id FROM devices WHERE host=? AND port=?',
                              (peer['virtual_ip'], row['port'] if row else 22)).fetchone()
        if endpoint and (not row or endpoint['id'] != row['id']):
            return {'projected': False, 'reason': 'endpoint_already_registered'}
        if not row:
            identifier = devices.insert_device(db, devices.DeviceInput(name=peer['name'], host=peer['virtual_ip'],
                                        platform=platform(peer['os']), access_mode='none', device_type='computer'))
            db.execute('UPDATE devices SET platform_override=0 WHERE id=?', (identifier,))
            row = db.execute('SELECT * FROM devices WHERE id=?', (identifier,)).fetchone()
        values = {'source': 'fabric', 'provider': identity, 'peer_id': peer_id,
                  'connection_status': 'revoked' if peer['revoked'] else ('online' if peer['data_plane_confirmed'] else 'unknown'),
                  'last_seen': datetime.fromtimestamp(peer['last_seen'], timezone.utc).isoformat() if peer['last_seen'] else None,
                  'synced_at': devices.now(), 'mesh_groups': json.dumps(peer['groups'])}
        if not row['name_override']:
            values['name'] = peer['name']
        if not row['platform_override']:
            values['platform'] = platform(peer['os'])
        if row['host'] != peer['virtual_ip']:
            values.update(host=peer['virtual_ip'], revision=row['revision'] + 1, status='unchecked', checked_at=None, latency_ms=None)
        db.execute('UPDATE devices SET ' + ','.join(key + '=?' for key in values) + ' WHERE id=?',
                   (*values.values(), row['id']))
        return {'projected': True, 'device_id': row['id']}


def project_all():
    with fabric.database() as db:
        identifiers = [row['id'] for row in db.execute('SELECT id FROM fabric_peers')]
    return [project(identifier) for identifier in identifiers]
