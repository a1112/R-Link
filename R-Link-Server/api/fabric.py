"""Authenticated fabric administration, machine control and opaque WSS relay."""
import asyncio
import json
import logging
import sqlite3
import uuid

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, Security, WebSocket, WebSocketDisconnect
from core import fabric, fabric_inventory
from core.auth import require_admin, require_auth, security

router = APIRouter(prefix='/api/fabric', tags=['fabric'])
logger = logging.getLogger(__name__)


def project_inventory(peer_id=None):
    # Enrollment/token issuance has already committed. Projection failures must
    # not strand a consumed enrollment without returning the machine credential.
    try:
        return fabric_inventory.project(peer_id) if peer_id else fabric_inventory.project_all()
    except (HTTPException, OSError, sqlite3.DatabaseError) as exc:
        logger.warning('Fabric inventory projection unavailable (%s)', type(exc).__name__)
        return {'projected': False, 'reason': 'projection_unavailable'}


def bearer(headers):
    value = headers.get('authorization', '')
    kind, _, token = value.partition(' ')
    if kind.lower() != 'bearer' or not token or ' ' in token:
        raise HTTPException(401, 'Valid fabric machine credential required')
    return token


def machine_auth(request: Request, credentials=Security(security)):
    # No browser session, master/service key, local-peer or forwarded-header fallback.
    return fabric.machine(bearer(request.headers))


@router.get('/status')
def status(user=Depends(require_auth)):
    return fabric.status()


@router.get('/peers')
def peers(user=Depends(require_auth)):
    return fabric.list_peers()


@router.patch('/peers/{peer_id}')
def update_peer(peer_id: str, data: fabric.PeerUpdate, user=Depends(require_admin)):
    result = fabric.update_peer(peer_id, data, user['id'])
    fabric.relay.invalidate_all()
    project_inventory(peer_id)
    return result


@router.post('/peers/{peer_id}/revoke')
def revoke_peer(peer_id: str, user=Depends(require_admin)):
    result = fabric.revoke_peer(peer_id, user['id'])
    fabric.relay.invalidate(peer_id)
    project_inventory(peer_id)
    return result


@router.get('/groups')
def groups(user=Depends(require_auth)):
    return fabric.list_groups()


@router.post('/groups', status_code=201)
def create_group(data: fabric.GroupInput, user=Depends(require_admin)):
    result = fabric.save_group(data, user['id'])
    fabric.relay.invalidate_all()
    project_inventory()
    return result


@router.put('/groups/{group_id}')
def update_group(group_id: str, data: fabric.GroupInput, user=Depends(require_admin)):
    result = fabric.save_group(data, user['id'], group_id)
    fabric.relay.invalidate_all()
    project_inventory()
    return result


@router.get('/enrollments')
def enrollments(user=Depends(require_admin)):
    return {'enrollments': fabric.list_enrollments()}


@router.post('/enrollments', status_code=201)
def create_enrollment(data: fabric.EnrollmentInput, user=Depends(require_admin)):
    return fabric.create_enrollment(data, user['id'])


@router.post('/enrollments/{enrollment_id}/revoke')
def revoke_enrollment(enrollment_id: str, user=Depends(require_admin)):
    return fabric.revoke_enrollment(enrollment_id, user['id'])


@router.post('/enrollment', status_code=201)
def enrollment(data: fabric.Enroll):
    result = fabric.enroll(data)
    result['inventory'] = project_inventory(result['peer_id'])
    return result


@router.get('/agent/config')
def agent_config(peer=Depends(machine_auth)):
    return fabric.agent_config(peer['id'])


@router.post('/agent/heartbeat')
def heartbeat(data: fabric.Heartbeat, peer=Depends(machine_auth)):
    result = fabric.heartbeat(peer['id'], data)
    result['inventory'] = project_inventory(peer['id'])
    return result


@router.websocket('/relay')
async def relay(websocket: WebSocket):
    # Query-string credentials leak into reverse-proxy/access logs and are forbidden.
    if websocket.query_params:
        await websocket.close(code=1008, reason='Relay credentials cannot use URL parameters')
        return
    connection = None
    accepted = False
    tasks = []
    try:
        if websocket.headers.get('authorization'):
            peer = fabric.machine(bearer(websocket.headers))
            await websocket.accept()
            accepted = True
        else:
            await websocket.accept()
            accepted = True
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=5)
            if len(raw) > 512:
                raise HTTPException(401, 'Relay authentication frame too large')
            message = json.loads(raw)
            if (not isinstance(message, dict) or set(message) != {'type', 'token'}
                    or message.get('type') != 'auth'):
                raise HTTPException(401, 'Relay authentication required')
            peer = fabric.machine(message['token'])
        connection = fabric.RelayConnection(peer['id'])
        fabric.relay.register(connection)
        limit = fabric.relay.rate_limit(peer['id'])

        async def send():
            while True:
                data = await connection.queue.get()
                if data is None:
                    raise HTTPException(401, 'Relay device revoked or configuration changed')
                await asyncio.wait_for(websocket.send_bytes(data), timeout=5)

        async def receive():
            while True:
                message = await websocket.receive()
                if message['type'] == 'websocket.disconnect':
                    return
                data = message.get('bytes')
                if not isinstance(data, bytes):
                    raise HTTPException(400, 'Relay requires binary frames after authentication')
                if not limit.allow(len(data)):
                    raise HTTPException(429, 'Relay rate limit exceeded')
                fabric.relay.forward(connection, data)

        async def guard():
            while True:
                await asyncio.sleep(1)
                # Revalidate even idle sockets after revocation, heartbeat expiry or another worker's mutation.
                current = fabric.machine_token_peer(peer['id'])
                if current is None:
                    raise HTTPException(401, 'Relay device revoked')
                if not fabric.peer_heartbeat_current(current):
                    raise HTTPException(401, 'Relay heartbeat expired')

        tasks = [asyncio.create_task(function()) for function in (send, receive, guard)]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except (HTTPException, ValueError, TypeError, asyncio.TimeoutError, RuntimeError):
        try:
            await websocket.close(code=1008, reason='Relay authorization, protocol or resource limit failed')
        except RuntimeError:
            pass
    finally:
        # Remove ownership before awaited cleanup, which ASGI shutdown may cancel.
        if connection:
            fabric.relay.unregister(connection)
        for task in tasks:
            task.cancel()
        # Shield cleanup from ASGI level cancellation, retaining a close deadline.
        with anyio.move_on_after(5, shield=True):
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if accepted:
                try:
                    await websocket.close()
                except RuntimeError:
                    pass
