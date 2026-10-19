"""R-Link authorization around the explicitly configured server-local Core."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import ClientDisconnect

from core import identity
from core.auth import authenticate, authenticate_current
from core.bridgeproxy import (
    BridgeProxy, CoreResponse, MAX_REQUEST_BYTES, READ_PATHS, WRITE_ROUTES, failure,
)

router = APIRouter(prefix='/api/bridgeproxy/v1', tags=['bridgeproxy'])


async def require_reader(user: dict = Depends(authenticate)):
    if identity.ROLES.get(user.get('role'), 0) < identity.ROLES['viewer']:
        raise HTTPException(403, 'viewer role required')
    return user


async def require_controller(user: dict = Depends(authenticate)):
    if user.get('role') != 'admin':
        raise HTTPException(403, 'admin role required')
    return user


def instance(request: Request) -> BridgeProxy:
    value = getattr(request.app.state, 'bridgeproxy', None)
    if value is None:
        raise HTTPException(503, 'Core adapter is not ready')
    return value


def response(value: CoreResponse):
    return JSONResponse(value.body, status_code=value.status, headers={
        **value.headers, 'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
    })


@router.get('/adapter', dependencies=[Depends(require_reader)])
async def adapter(request: Request):
    return response(instance(request).adapter())


async def request_body(request: Request):
    if request.query_params or b'%' in request.scope.get('raw_path', b''):
        return failure(400, 'invalid_core_path', 'Core 接口不接受查询参数或编码路径')
    for name in ('if-match', 'idempotency-key'):
        if len(request.headers.getlist(name)) > 1:
            return failure(400, 'duplicate_core_header', '配置版本或幂等键不可重复')
    raw = bytearray()
    try:
        async with asyncio.timeout(5):
            async for chunk in request.stream():
                if len(raw) + len(chunk) > MAX_REQUEST_BYTES:
                    return failure(413, 'body_too_large', '请求体超过 1 MiB')
                raw.extend(chunk)
    except TimeoutError:
        return failure(408, 'incomplete_body', '请求体读取超时')
    except ClientDisconnect:
        return failure(499, 'request_cancelled', '请求已取消')
    if raw:
        parts = [part.strip().lower() for part in request.headers.get('content-type', '').split(';')]
        if parts[0] != 'application/json' or any(part != 'charset=utf-8' for part in parts[1:]):
            return failure(415, 'unsupported_media_type', '非空请求体必须为 UTF-8 application/json')
    return bytes(raw)


def current_permission(request: Request, control: bool):
    scheme, _, token = request.headers.get('authorization', '').partition(' ')
    credentials = (HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
                   if scheme.lower() == 'bearer' else None)
    # Body reading can yield; an earlier role/session snapshot cannot authorize
    # a later privileged Core dispatch after revocation.
    user = authenticate_current(request, credentials)
    minimum = 'admin' if control else 'viewer'
    if identity.ROLES.get(user.get('role'), 0) < identity.ROLES[minimum]:
        raise HTTPException(403, minimum + ' role required')


def handler(method: str, path: str, *, control: bool = False, sas: bool = False):
    async def forward(request: Request):
        body = await request_body(request)
        if isinstance(body, CoreResponse):
            return response(body)
        current_permission(request, control or method != 'GET')
        upstream_path = path.format(**request.path_params)
        result = await instance(request).request(
            method, upstream_path, body=body, if_match=request.headers.get('if-match'),
            idempotency_key=request.headers.get('idempotency-key'), control=control,
            allow_sas=sas,
            authorize=lambda: current_permission(request, control or method != 'GET'),
        )
        return response(result)
    return forward


# The SAS view is an explicit privileged alias. All ordinary GETs use read scope
# and strip pairing verification codes, including snapshots and operation lists.
router.add_api_route('/pairings/control', handler('GET', '/pairings', control=True, sas=True),
                     methods=['GET'], dependencies=[Depends(require_controller)])
for _path in READ_PATHS:
    router.add_api_route(_path, handler('GET', _path), methods=['GET'],
                         dependencies=[Depends(require_reader)])
for _method, _path in WRITE_ROUTES:
    router.add_api_route(_path, handler(_method, _path), methods=[_method],
                         dependencies=[Depends(require_controller)])
