"""Bounded HTTP framing; authentication remains with the enclosing native app."""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request

from ._vendor.r_sdk_interop import MAX_BYTES


async def request_text(request: Request) -> str:
    """Bound body delivery before passing exact bytes to the SDK strict parser."""

    async def read() -> bytes:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise HTTPException(413, "SCHEMA_INVALID")
        return bytes(body)

    try:
        return (await asyncio.wait_for(read(), 5)).decode("utf-8")
    except TimeoutError:
        raise HTTPException(408, "TIMEOUT") from None
    except UnicodeError:
        raise HTTPException(400, "SCHEMA_INVALID") from None
