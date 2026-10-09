"""Opt-in R-SDK read bridge using R-Link's own authentication and inventory."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from core import identity
from core.auth import authenticate_current
from interop_bridge import ContractError, ReadService, Settings, validate
from interop_bridge.binding import ReadView
from interop_bridge.http import request_text
from interop_bridge.service import Recheck, problem

router = APIRouter(prefix="/api/interop/v1", tags=["interop-read"])
Json = dict[str, Any]


async def inventory(request: ReadView) -> Json:
    """Inventory metadata cannot establish the required remote ServiceDescriptor."""
    raise ContractError("NO_ADAPTER")


def service(request: Request) -> ReadService:
    """Keep read lifecycle state in the R-Link application, not a global grant cache."""
    instance = getattr(request.app.state, "interop_read_service", None)
    if instance is None:
        settings = Settings.from_env(
            "R_LINK_INTEROP", "r-link", "r-link.devices.list", "devices"
        )
        instance = ReadService(settings, inventory, available=False)
        request.app.state.interop_read_service = instance
    return instance


def native_actor(request: Request) -> str:
    """Read the current native role/session; a previous async boolean is insufficient."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    credentials = (
        HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
        if scheme.lower() == "bearer"
        else None
    )
    try:
        user = authenticate_current(request, credentials)
    except HTTPException:
        raise ContractError("UNAUTHENTICATED") from None
    if identity.ROLES.get(str(user.get("role") or "pending"), 0) < identity.ROLES["viewer"]:
        raise ContractError("FORBIDDEN")
    return str(user["id"]) + ":" + str(user.get("session_id", user["principal"]))


def native_recheck(request: Request, owner: str) -> Recheck:
    """Linearize a fresh native actor/session read at dispatch and output release."""
    def recheck(frame: ReadView) -> bool:
        return native_actor(request) == owner

    return recheck


async def native_context(
    request: Request,
) -> tuple[str, Callable[[ReadView], Awaitable[bool]]]:
    """Resolve and freshly recheck the existing native principal and session."""
    owner = native_actor(request)
    recheck = native_recheck(request, owner)

    async def authorize(frame: ReadView) -> bool:
        return recheck(frame)

    return owner, authorize


@router.post("/messages")
async def exchange(request: Request) -> JSONResponse:
    """Use the exact owner envelope; caller snapshots never grant R-Link access."""
    try:
        owner, authorize = await native_context(request)
        result = await service(request).exchange(
            await request_text(request),
            owner,
            authorize,
            recheck=native_recheck(request, owner),
            respond_async=request.headers.get("prefer") == "respond-async",
        )
    except ContractError as error:
        raise HTTPException(problem(error.code)["status"], error.code) from None
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/descriptor")
async def descriptor(request: Request) -> JSONResponse:
    """Return actual local capability metadata after native authentication."""
    try:
        deadline = asyncio.get_running_loop().time() + 5
        owner, authorize = await native_context(request)
        recheck = native_recheck(request, owner)
        instance = service(request)
        result = instance.settings.envelope(
            "service.descriptor", instance.settings.descriptor(instance.available)
        )
        await instance.check(result, authorize, deadline, recheck=recheck)
        validate(result)
        response = JSONResponse(result, headers={"Cache-Control": "no-store"})
        instance.commit(result, recheck, deadline)
    except ContractError as error:
        raise HTTPException(problem(error.code)["status"], error.code) from None
    return response
