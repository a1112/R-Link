"""Unified device inventory and real NetBird lifecycle management."""
import asyncio
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from core.auth import require_auth
from core import devices
from core.device_sync import onboarding

router = APIRouter(prefix='/api/devices', tags=['devices'], dependencies=[Depends(require_auth)])
_inflight: set[str] = set()


def manager(request):
    return request.app.state.device_sync


@router.get('')
def list_devices():
    return devices.list_devices()


@router.post('', status_code=201)
async def create_device(data: devices.DeviceInput, request: Request):
    sync = manager(request)
    async with sync.lock:
        result = await run_in_threadpool(devices.save_device, data)
        sync.audit('create', result['id'])
        return result


@router.get('/export')
def export_devices(version: int = 1):
    return devices.export_inventory(version)


@router.post('/import')
async def import_devices(data: devices.DeviceInventory, request: Request):
    sync = manager(request)
    async with sync.lock:
        result = await run_in_threadpool(devices.import_inventory, data)
        sync.audit('import', 'inventory')
        return result


@router.get('/management-status')
def management_status(request: Request):
    return manager(request).status()


@router.get('/onboarding')
def device_onboarding():
    return onboarding()


@router.post('/sync')
async def sync_devices(request: Request):
    return await manager(request).sync()


class PeerLinkInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    peer_id: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')


@router.post('/{device_id}/link')
async def link_device(device_id: str, data: PeerLinkInput, request: Request):
    return await manager(request).link(device_id, data.peer_id)


@router.post('/{device_id}/revoke')
async def revoke_device(device_id: str, request: Request):
    return await manager(request).revoke(device_id)


@router.get('/{device_id}')
def get_device(device_id: str):
    return devices.read_device(device_id)


@router.put('/{device_id}')
async def update_device(device_id: str, data: devices.DeviceInput, request: Request):
    sync = manager(request)
    async with sync.lock:
        result = await run_in_threadpool(devices.save_device, data, device_id)
        sync.audit('update', device_id)
        return result


@router.delete('/{device_id}', status_code=204)
async def delete_device(device_id: str, request: Request):
    sync = manager(request)
    async with sync.lock:
        await run_in_threadpool(devices.delete_device, device_id)
        sync.audit('delete', device_id)
        return Response(status_code=204)


@router.post('/{device_id}/probe')
async def probe_device(device_id: str, request: Request = None):
    if device_id in _inflight or len(_inflight) >= 8:
        raise HTTPException(429, 'A check is already running; retry shortly')
    _inflight.add(device_id)
    writer = None
    try:
        device = await run_in_threadpool(devices.read_device, device_id)
        start = time.monotonic()
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(device['host'], device['port']), timeout=3)
            reachable = True
        except (OSError, asyncio.TimeoutError):
            reachable = False
        elapsed = round((time.monotonic() - start) * 1000, 2)
        if request is not None:
            async with manager(request).lock:
                return await run_in_threadpool(devices.record_probe, device, reachable, elapsed)
        return await run_in_threadpool(devices.record_probe, device, reachable, elapsed)
    finally:
        try:
            if writer:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=1)
                except (OSError, asyncio.TimeoutError):
                    pass
        finally:
            _inflight.discard(device_id)
