"""Independent OIDC BFF and explicit R-Link role administration."""
import hmac
import secrets
import time
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from core import identity
from core.auth import access_manager, authenticate, require_admin, require_operator, security, allowed_origins

router = APIRouter(prefix='/api/auth', tags=['authentication'])


class WebSocketTokenResponse(BaseModel):
    token: str
    scope: str
    expires_in: int


@router.get('/config')
def auth_config():
    return {'mode': identity.mode(), 'login_enabled': identity.configured(),
            'desktop_login_enabled': identity.configured()}


@router.get('/session')
async def session(request: Request, credentials: HTTPAuthorizationCredentials | None = Security(security)):
    try:
        user = await authenticate(request, credentials)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        user = None
    is_user = bool(user and user.get('principal') == 'user')
    return {'mode': identity.mode(), 'authenticated': is_user if identity.enabled() else user is not None,
            'user': identity.public_user(user) if is_user else None,
            'csrf_token': user.get('csrf') if user else None,
            'session_context': user.get('session_id') if user else None,
            'expires_at': user.get('expires_at') if user else None}


async def oidc_client():
    config = identity.settings()
    oauth = OAuth()
    remote = oauth.register('idp', client_id=config['client_id'], client_secret=config['client_secret'],
                            server_metadata_url=config['issuer'].rstrip('/') + '/.well-known/openid-configuration',
                            client_kwargs={'scope': 'openid profile email', 'code_challenge_method': 'S256',
                                           'timeout': 15, 'follow_redirects': False, 'trust_env': False})
    metadata = await remote.load_server_metadata()
    if metadata.get('issuer') != config['issuer']:
        raise HTTPException(503, 'OIDC discovery issuer does not match the configured issuer')
    supported = {'RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512', 'PS256', 'PS384', 'PS512', 'EdDSA'}
    algorithms = [value for value in metadata.get('id_token_signing_alg_values_supported', ['RS256'])
                  if value in supported]
    if not algorithms:
        raise HTTPException(503, 'OIDC provider has no supported signing algorithms')
    metadata['id_token_signing_alg_values_supported'] = algorithms
    metadata['follow_redirects'] = False
    metadata['trust_env'] = False
    for field in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
        value = metadata.get(field, '')
        parsed = urlsplit(value)
        if (any(ord(char) <= 32 or char == '\\' for char in value) or parsed.scheme != 'https'
                or not parsed.hostname or parsed.username or parsed.password or parsed.fragment):
            raise HTTPException(503, 'OIDC provider endpoint must use HTTPS')
        if (parsed.scheme, parsed.netloc.lower()) != (urlsplit(config['issuer']).scheme,
                                                       urlsplit(config['issuer']).netloc.lower()):
            raise HTTPException(503, 'OIDC endpoints must belong to the configured issuer origin')
    return remote


def oidc_enabled():
    if not identity.enabled():
        raise HTTPException(404, 'OIDC login is not enabled')
    identity.settings()


def trusted_desktop_origin(request: Request):
    origin = request.headers.get('origin')
    public_origin = '/'.join(identity.settings()['public_url'].split('/')[:3])
    if origin and origin not in set(allowed_origins()) | {public_origin}:
        raise HTTPException(403, 'Untrusted desktop origin')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Cross-site desktop request rejected')


async def begin_login(request: Request, desktop_id: str | None = None):
    oidc_enabled()
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Cross-site login rejected')
    config = identity.settings()
    previous_session = request.cookies.get(identity.SESSION_COOKIE)
    parent = identity.digest(previous_session) if previous_session else None
    if parent and not identity.session_from_hash(parent):
        # A stale tab cannot silently start a new family after another tab logged out.
        response = HTMLResponse('<!doctype html><html lang="zh"><meta charset="utf-8">'
                                '<title>R-Link</title><p>登录状态已更改，请返回 R-Link 首页重新登录。</p></html>',
                                status_code=409)
        response.delete_cookie(identity.SESSION_COOKIE, **identity.cookie_settings())
        return response
    try:
        remote = await oidc_client()
        state, nonce, verifier, binding = (secrets.token_urlsafe(32) for _ in range(4))
        authorization = await remote.create_authorization_url(config['callback'], state=state,
                                                               nonce=nonce, code_verifier=verifier)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Identity provider unavailable')
    with identity.database() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT COUNT(*) FROM flows').fetchone()[0] >= 1000:
            raise HTTPException(429, 'Too many pending logins')
        if desktop_id:
            result = db.execute('UPDATE desktop_flows SET started=1 WHERE id=? AND started=0', (desktop_id,))
            if result.rowcount != 1:
                raise HTTPException(400, 'Desktop login expired or already started')
        previous_binding = request.cookies.get(identity.FLOW_COOKIE)
        if previous_binding:
            db.execute('DELETE FROM flows WHERE binding=?', (identity.digest(previous_binding),))
        if parent and not db.execute('SELECT id FROM sessions WHERE id=? AND current=1', (parent,)).fetchone():
            raise HTTPException(409, 'SESSION_CHANGED')
        db.execute('INSERT INTO flows(state,binding,nonce,verifier,desktop_id,expires_at,parent_session) VALUES (?,?,?,?,?,?,?)',
                   (identity.digest(state), identity.digest(binding), identity.encrypt_flow(nonce),
                    identity.encrypt_flow(verifier), desktop_id, int(time.time()) + 300, parent))
    response = RedirectResponse(authorization['url'], status_code=302)
    response.set_cookie(identity.FLOW_COOKIE, binding, max_age=300, **identity.cookie_settings())
    return response


@router.get('/login')
async def login(request: Request):
    return await begin_login(request)


@router.get('/callback')
async def callback(request: Request):
    oidc_enabled()
    for parameter in ('state', 'code', 'error', 'iss'):
        if len(request.query_params.getlist(parameter)) > 1:
            raise HTTPException(400, 'Duplicate callback parameter')
    if request.query_params.get('iss') not in {None, identity.settings()['issuer']}:
        raise HTTPException(400, 'Unexpected callback issuer')
    state = identity.digest(request.query_params.get('state', ''))
    code = request.query_params.get('code', '')
    binding = request.cookies.get(identity.FLOW_COOKIE, '')
    with identity.database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM flows WHERE state=? AND used=0', (state,)).fetchone()
        if not row or not binding or not hmac.compare_digest(row['binding'], identity.digest(binding)):
            raise HTTPException(400, 'Login expired or browser binding invalid')
        flow = dict(row)
        db.execute('UPDATE flows SET used=1 WHERE state=?', (state,))
    try:
        if request.query_params.get('error') or not code or len(code) > 4096:
            raise HTTPException(400, 'Provider login did not complete')
        remote = await oidc_client()
        nonce, verifier = identity.decrypt_flow(flow['nonce']), identity.decrypt_flow(flow['verifier'])
        token = await remote.fetch_access_token(redirect_uri=identity.settings()['callback'], code=code,
                                               code_verifier=verifier)
        if not token.get('id_token'):
            raise HTTPException(400, 'Provider did not return an ID token')
        claims = await remote.parse_id_token(token, nonce=nonce, leeway=30,
                                              claims_options={'iss': {'essential': True,
                                                                      'value': identity.settings()['issuer']},
                                                              'aud': {'essential': True,
                                                                      'value': identity.settings()['client_id']}})
        if not claims or claims.get('nonce') != nonce:
            raise HTTPException(400, 'Invalid login nonce')
        audience = claims.get('aud', [])
        audience = [audience] if isinstance(audience, str) else audience
        if not isinstance(audience, list) or identity.settings()['client_id'] not in audience:
            raise HTTPException(400, 'Invalid ID token audience')
        user = identity.upsert_identity(dict(claims))
        with identity.database() as db:
            db.execute('BEGIN IMMEDIATE')
            valid = db.execute('DELETE FROM flows WHERE state=? AND used=1 AND binding=?',
                               (state, identity.digest(binding)))
            if valid.rowcount != 1:
                raise HTTPException(400, 'Login was cancelled')
            if flow['desktop_id']:
                ready = db.execute('UPDATE desktop_flows SET user_id=? WHERE id=? AND started=1',
                                   (user['id'], flow['desktop_id']))
                if ready.rowcount != 1:
                    raise HTTPException(400, 'Desktop login expired')
                response = HTMLResponse('<!doctype html><html lang="zh"><meta charset="utf-8">'
                                        '<title>R-Link</title><p>已完成 R-Link 登录，可以返回桌面客户端。</p></html>')
            else:
                session_info = identity.create_session_in_db(db, user['id'], parent_session=flow['parent_session'])
                response = RedirectResponse(identity.settings()['public_url'] + '/', status_code=302)
                response.set_cookie(identity.SESSION_COOKIE, session_info['token'],
                                    max_age=session_info['expires_at'] - int(time.time()), **identity.cookie_settings())
        return response
    except Exception as exc:
        with identity.database() as db:
            db.execute('DELETE FROM flows WHERE state=?', (state,))
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(400, 'OIDC login validation failed')


class DesktopExchange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    flow_id: str = Field(min_length=20, max_length=100)
    poll_secret: str = Field(min_length=20, max_length=100)


@router.post('/desktop/start')
def desktop_start(request: Request):
    oidc_enabled()
    trusted_desktop_origin(request)
    flow_id, secret = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    with identity.database() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT COUNT(*) FROM desktop_flows').fetchone()[0] >= 1000:
            raise HTTPException(429, 'Too many pending desktop logins')
        db.execute('INSERT INTO desktop_flows(id,secret,expires_at) VALUES (?,?,?)',
                   (flow_id, identity.digest(secret), int(time.time()) + 300))
    return {'login_url': identity.settings()['public_url'] + '/api/auth/desktop/login?flow_id=' + flow_id,
            'flow_id': flow_id, 'poll_secret': secret, 'expires_in': 300}


@router.get('/desktop/login')
async def desktop_login(request: Request, flow_id: str):
    return await begin_login(request, flow_id)


@router.post('/desktop/exchange')
def desktop_exchange(data: DesktopExchange, request: Request):
    oidc_enabled()
    trusted_desktop_origin(request)
    with identity.database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM desktop_flows WHERE id=?', (data.flow_id,)).fetchone()
        if not row or not hmac.compare_digest(row['secret'], identity.digest(data.poll_secret)):
            raise HTTPException(400, 'Desktop login expired or secret invalid')
        if not row['user_id']:
            return JSONResponse({'pending': True}, status_code=202)
        user = db.execute('SELECT * FROM users WHERE id=?', (row['user_id'],)).fetchone()
        session_info = identity.create_session_in_db(db, row['user_id'], 'desktop')
        db.execute('DELETE FROM desktop_flows WHERE id=?', (data.flow_id,))
        return {'token': session_info['token'], 'expires_at': session_info['expires_at'],
                'user': identity.public_user(user)}


async def disconnect_sessions(*, user_id=None, session_id=None):
    from api.ssh import active_connections
    for connection in list(active_connections.values()):
        claims = connection.websocket.scope.get('r_link_ws_claims', {})
        if ((user_id and claims.get('sub') == user_id) or
                (session_id and claims.get('session_id') == session_id)):
            await connection.close()


@router.post('/logout', status_code=204)
async def logout(request: Request, user: dict = Depends(authenticate)):
    if user.get('principal') != 'user':
        raise HTTPException(400, 'No user session to revoke')
    identity.revoke_session(user['session_id'])
    binding = request.cookies.get(identity.FLOW_COOKIE)
    if binding:
        with identity.database() as db:
            db.execute('DELETE FROM flows WHERE binding=?', (identity.digest(binding),))
    await disconnect_sessions(session_id=user['session_id'])
    response = Response(status_code=204)
    response.delete_cookie(identity.SESSION_COOKIE, **identity.cookie_settings())
    response.delete_cookie(identity.FLOW_COOKIE, **identity.cookie_settings())
    return response


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['pending', 'viewer', 'operator', 'admin'] | None = None
    disabled: bool | None = None


@router.get('/users')
async def users(user: dict = Depends(require_admin)):
    return {'users': identity.list_users()}


@router.patch('/users/{user_id}')
async def change_user(user_id: str, changes: UserUpdate, actor: dict = Depends(require_admin)):
    data = changes.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(400, 'A role or disabled flag is required')
    result = identity.update_user(user_id, data, actor['id'])
    await disconnect_sessions(user_id=user_id)
    return result


@router.post('/ws-token', response_model=WebSocketTokenResponse)
async def issue_websocket_token(user: dict = Depends(require_operator)):
    token = await access_manager.issue_websocket_token(user, scope='ssh', ttl_seconds=60)
    return WebSocketTokenResponse(token=token, scope='ssh', expires_in=60)
