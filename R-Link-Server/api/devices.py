"""Manage explicitly registered devices; no subnet scanning or shell-based ping."""
import asyncio
import time
from fastapi import APIRouter, Depends, HTTPException, Response
from starlette.concurrency import run_in_threadpool
from core.auth import require_auth
from core import devices

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(require_auth)])
_inflight: set[str] = set()

@router.get("")
def list_devices():
    return devices.list_devices()

@router.post("", status_code=201)
def create_device(data: devices.DeviceInput):
    return devices.save_device(data)

@router.put("/{device_id}")
def update_device(device_id: str, data: devices.DeviceInput):
    return devices.save_device(data, device_id)

@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: str):
    devices.delete_device(device_id)
    return Response(status_code=204)

@router.post("/{device_id}/probe")
async def probe_device(device_id: str):
    if device_id in _inflight or len(_inflight) >= 8:
        raise HTTPException(429, "A check is already running; retry shortly")
    _inflight.add(device_id)
    writer = None
    try:
        def read():
            with devices.database() as db:
                return devices.get_device(db, device_id)
        device = await run_in_threadpool(read)
        start = time.monotonic()
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(device["host"], device["port"]), timeout=3)
            reachable = True
        except (OSError, asyncio.TimeoutError):
            reachable = False
        elapsed = round((time.monotonic() - start) * 1000, 2)
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
