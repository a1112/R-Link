"""Authenticated QoS configuration and Linux tc/IFB control routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request

try:
    from core.auth import require_access
except ImportError:  # pragma: no cover
    from core.auth import require_auth as require_access

from core.qos import QoSApplyRequest, QoSConfigUpdate, QoSManager


router = APIRouter(prefix="/api/qos", tags=["qos"], dependencies=[Depends(require_access)])


def manager(request: Request) -> QoSManager:
    instance = getattr(request.app.state, "services", None)
    qos = getattr(instance, "qos", None) if instance is not None else None
    if qos is None or not getattr(instance, "ready", False):
        raise HTTPException(503, "后台服务尚未就绪")
    return qos


@router.get("/status")
def get_status(request: Request):
    return manager(request).status()


@router.put("/config")
def put_config(data: QoSConfigUpdate, request: Request):
    return manager(request).put_config(data.expected_revision, data.config)


@router.post("/apply")
async def apply_config(data: QoSApplyRequest, request: Request):
    return await manager(request).apply(data.expected_revision)


@router.delete("/applied")
async def clear_applied(
    request: Request,
    expected_revision: int = Query(..., ge=1),
):
    return await manager(request).clear_applied(expected_revision)
