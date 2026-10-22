"""Local compatibility, OIDC sessions, role gates and one-use SSH tickets."""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import time
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core import identity

security = HTTPBearer(auto_error=False)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_ORIGINS = "http://127.0.0.1:4322,http://localhost:4322,tauri://localhost,http://tauri.localhost"


def allowed_origins() -> list[str]:
    return [origin.strip() for origin in os.getenv("R_LINK_CORS_ORIGINS", DEFAULT_ORIGINS).split(",") if origin.strip()]


def is_loopback(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or bool(getattr(address, "ipv4_mapped", None) and address.ipv4_mapped.is_loopback)
    except ValueError:
        return False


def server_host() -> str:
    host = os.getenv("R_LINK_HOST", "127.0.0.1")
    if host not in LOCAL_HOSTS and not os.getenv("R_LINK_API_TOKEN") and not identity.configured():
        raise RuntimeError("Configure OIDC or R_LINK_API_TOKEN before binding to a non-loopback address")
    return host


class LocalAuth:
    def __init__(self):
        self.websocket_secret = os.getenv("R_LINK_WS_TOKEN_SECRET") or secrets.token_urlsafe(48)

    async def issue_websocket_token(
        self,
        user: Dict[str, Any],
        *,
        scope: str,
        ttl_seconds: int = 60,
    ) -> str:
        """签发短时效 WebSocket 票据。"""
        now = int(time.time())
        payload = {
            "sub": user.get("id"),
            "scope": scope,
            "iat": now,
            "exp": now + ttl_seconds,
            "nonce": secrets.token_urlsafe(8),
            "session_id": user.get('session_id'),
            "principal": user.get('principal', 'local'),
        }
        return self._encode_websocket_token(payload)

    async def verify_websocket_token(
        self,
        token: str,
        *,
        expected_scope: str,
    ) -> Optional[Dict[str, Any]]:
        """校验短时效 WebSocket 票据。"""
        payload = self._decode_websocket_token(token)
        if payload is None:
            return None

        if payload.get("scope") != expected_scope:
            return None

        exp = payload.get("exp")
        sub = payload.get("sub")
        if type(exp) is not int or exp <= int(time.time()) or not isinstance(sub, str) or not sub:
            return None

        if not self.websocket_identity_valid(payload):
            return None
        if not identity.consume_websocket_nonce(payload.get('nonce', ''), exp):
            return None
        return payload

    def websocket_identity_valid(self, payload: dict) -> bool:
        """Recheck the backing session even after the ticket was redeemed."""
        if payload.get('session_id'):
            user = identity.session_from_hash(payload['session_id'])
            return bool(user and user['id'] == payload.get('sub')
                        and identity.ROLES.get(user['role'], 0) >= identity.ROLES['operator'])
        if payload.get('principal') == 'service':
            key = os.getenv('R_LINK_API_TOKEN', '')
            return bool(key and payload.get('sub') == service_identity(key)['id'])
        return not identity.enabled() and not os.getenv('R_LINK_API_TOKEN')

    def _encode_websocket_token(self, payload: Dict[str, Any]) -> str:
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
        signature = hmac.new(
            self.websocket_secret.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        return f"{payload_b64}.{signature_b64}"

    def _decode_websocket_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not isinstance(token, str) or not token.isascii():
            return None
        try:
            payload_b64, signature_b64 = token.split(".", 1)
        except ValueError:
            return None

        expected_signature = hmac.new(
            self.websocket_secret.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_signature).decode("ascii").rstrip("=")
        if not hmac.compare_digest(signature_b64, expected_b64):
            return None

        padding = "=" * (-len(payload_b64) % 4)
        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
            payload = json.loads(payload_bytes.decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None


access_manager = LocalAuth()


def service_identity(token: str) -> dict:
    return {'id': 'service-' + hashlib.sha256(token.encode()).hexdigest()[:24],
            'role': 'admin', 'principal': 'service'}


async def authenticate(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Dict[str, Any]:
    """Resolve the current native identity while retaining FastAPI dependency injection."""
    return authenticate_current(request, credentials)


def authenticate_current(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Dict[str, Any]:
    """OIDC never falls back to local access; cookies cannot inherit a service key."""
    if identity.enabled():
        cookie = request.cookies.get(identity.SESSION_COOKIE)
        if cookie:
            route = request.scope.get('route')
            user = identity.read_session(cookie, allow_retired=bool(route and route.path == '/api/auth/logout'))
            if not user or user['kind'] != 'browser':
                raise HTTPException(401, 'Session expired or revoked')
            if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                if request.headers.get('x-r-link-session-context') != user['session_id']:
                    raise HTTPException(409, 'SESSION_CHANGED')
                csrf = request.headers.get('x-r-link-csrf', '')
                if not csrf or not hmac.compare_digest(csrf.encode(), user['csrf'].encode()):
                    raise HTTPException(403, 'CSRF token required')
                expected_origin = str(identity.settings()['public_url']).split('/')[0:3]
                expected_origin = '/'.join(expected_origin)
                if request.headers.get('origin') != expected_origin:
                    raise HTTPException(403, 'Untrusted request origin')
            user['principal'] = 'user'
            return user
        if credentials:
            key = os.getenv('R_LINK_API_TOKEN', '')
            if key and hmac.compare_digest(credentials.credentials.encode(), key.encode()):
                return service_identity(key)
            user = identity.read_session(credentials.credentials)
            if user and user['kind'] == 'desktop':
                if (request.method not in {'GET', 'HEAD', 'OPTIONS'}
                        and request.headers.get('x-r-link-session-context') != user['session_id']):
                    raise HTTPException(409, 'SESSION_CHANGED')
                user['principal'] = 'user'
                return user
        raise HTTPException(401, 'Sign in required', headers={'WWW-Authenticate': 'Bearer'})

    configured_token = os.getenv("R_LINK_API_TOKEN", "")
    if configured_token:
        if credentials and hmac.compare_digest(credentials.credentials.encode(), configured_token.encode()):
            return service_identity(configured_token)
        raise HTTPException(401, "Service access key required", headers={"WWW-Authenticate": "Bearer"})

    origin = request.headers.get("origin")
    # Check the peer, Host and browser origin together; a local proxy alone is not authentication.
    if (request.client and is_loopback(request.client.host)
            and request.url.hostname in LOCAL_HOSTS
            and (not origin or origin in allowed_origins() or origin == str(request.base_url).rstrip("/"))
            and (origin or request.headers.get("sec-fetch-site") != "cross-site")):
        return {"id": "local-operator", 'role': 'admin', 'principal': 'local'}
    raise HTTPException(401, "Local access only; configure a service access key for remote use")


def viewer_route(request: Request) -> bool:
    if request.method != 'GET':
        return False
    path = request.scope.get('route').path if request.scope.get('route') else request.url.path
    return path in {
        '/api/devices', '/api/devices/{device_id}', '/api/mesh/status', '/api/mesh/peers',
        '/api/mesh/groups', '/api/system/info', '/api/system/resources', '/api/system/uptime',
        '/api/system/network',
        '/api/fabric/status', '/api/fabric/peers', '/api/fabric/groups',
    }


async def require_auth(request: Request, user: dict = Depends(authenticate)) -> dict:
    minimum = 'viewer' if viewer_route(request) else 'operator'
    path = request.scope.get('route').path if request.scope.get('route') else request.url.path
    if (path == '/api/audit' or path.startswith('/api/domains') or path.startswith('/api/tunnels')
            or path.startswith('/api/mesh/setup-keys')
            or path in {'/api/devices/{device_id}/revoke', '/api/devices/{device_id}/link'}
            or (path.startswith('/api/mesh/') and request.method not in {'GET', 'HEAD', 'OPTIONS'})):
        minimum = 'admin'
    if identity.ROLES.get(user.get('role'), 0) < identity.ROLES[minimum]:
        raise HTTPException(403, f'{minimum} role required')
    return user


async def require_operator(user: dict = Depends(authenticate)) -> dict:
    if identity.ROLES.get(user.get('role'), 0) < identity.ROLES['operator']:
        raise HTTPException(403, 'operator role required')
    return user


async def require_admin(user: dict = Depends(authenticate)) -> dict:
    if user.get('role') != 'admin':
        raise HTTPException(403, 'admin role required')
    return user


async def require_plugin_admin(request: Request, user: dict = Depends(authenticate)) -> dict:
    path = request.scope.get('route').path if request.scope.get('route') else request.url.path
    minimum = 'operator' if request.method == 'GET' and path == '/api/plugins/status/all' else 'admin'
    if identity.ROLES.get(user.get('role'), 0) < identity.ROLES[minimum]:
        raise HTTPException(403, f'{minimum} role required')
    return user
