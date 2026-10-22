"""Authenticated, bounded APIs for the Clash/Mihomo integration."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

try:
    # Newer service builds expose the same local/operator gate as
    # ``require_access``.  Keep compatibility with this checkout's historical
    # ``require_auth`` name without weakening the dependency.
    from core.auth import require_access
except ImportError:  # pragma: no cover - compatibility for older R-Link builds
    from core.auth import require_auth as require_access
from core.clash import (
    ClashConfigPatch,
    ClashManager,
    ClashProfileInput,
    ClashProfileStart,
    ClashSettingsInput,
    ProxySelection,
)


router = APIRouter(prefix="/api/clash", tags=["clash"], dependencies=[Depends(require_access)])


def manager(request: Request) -> ClashManager:
    instance = getattr(request.app.state, "services", None)
    clash = getattr(instance, "clash", None) if instance is not None else None
    if clash is None or not instance.ready:
        from fastapi import HTTPException
        raise HTTPException(503, "后台服务尚未就绪")
    return clash


@router.get("/settings")
async def get_settings(request: Request):
    return manager(request).settings()


@router.put("/settings")
async def put_settings(data: ClashSettingsInput, request: Request):
    return await manager(request).save_settings(data)


@router.get("/status")
async def get_status(request: Request):
    return await manager(request).status()


@router.get("/configs")
async def get_configs(request: Request):
    return await manager(request).configs()


@router.patch("/configs")
async def patch_configs(data: ClashConfigPatch, request: Request):
    return await manager(request).patch_configs(data)


@router.get("/proxies")
async def get_proxies(request: Request):
    return await manager(request).proxies()


@router.put("/proxies/{name:path}", status_code=204)
async def select_proxy(
    data: ProxySelection,
    request: Request,
    name: Annotated[str, Path(min_length=1, max_length=512)],
):
    await manager(request).select_proxy(name, data)
    return Response(status_code=204)


@router.get("/proxies/{name:path}/delay")
async def proxy_delay(
    request: Request,
    name: Annotated[str, Path(min_length=1, max_length=512)],
    timeout: Annotated[int, Query(ge=100, le=30000)] = 5000,
):
    return await manager(request).proxy_delay(name, timeout)


@router.get("/rules")
async def get_rules(request: Request):
    return await manager(request).rules()


@router.get("/connections")
async def get_connections(request: Request):
    return await manager(request).connections()


@router.get("/traffic")
async def get_traffic(request: Request):
    return await manager(request).traffic()


@router.delete("/connections", status_code=204)
async def close_all_connections(
    request: Request,
    source_id: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
):
    await manager(request).close_connections(source_id=source_id)
    return Response(status_code=204)


@router.delete("/connections/{identifier:path}", status_code=204)
async def close_connection(
    request: Request,
    identifier: Annotated[str, Path(min_length=1, max_length=512)],
    source_id: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
):
    await manager(request).close_connections(identifier, source_id=source_id)
    return Response(status_code=204)


@router.get("/providers/proxies")
async def get_proxy_providers(request: Request):
    return await manager(request).providers()


@router.put("/providers/proxies/{name:path}", status_code=204)
async def refresh_proxy_provider(
    request: Request,
    name: Annotated[str, Path(min_length=1, max_length=512)],
):
    await manager(request).refresh_provider(name)
    return Response(status_code=204)


@router.get("/profiles")
async def get_profiles(request: Request):
    return manager(request).profiles()


@router.post("/profiles", status_code=201)
async def create_profile(data: ClashProfileInput, request: Request):
    return await manager(request).save_profile(data)


@router.delete("/profiles/{identifier}", status_code=204)
async def remove_profile(
    request: Request,
    identifier: Annotated[str, Path(min_length=1, max_length=128)],
):
    await manager(request).delete_profile(identifier)
    return Response(status_code=204)


@router.post("/managed/start")
async def start_managed(data: ClashProfileStart, request: Request):
    return await manager(request).start_managed(data.profile_id)


@router.post("/managed/stop")
async def stop_managed(request: Request):
    return await manager(request).stop_managed()
