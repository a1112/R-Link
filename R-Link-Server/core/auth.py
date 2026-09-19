"""Local service access and short-lived SSH tickets; no external identity provider."""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import time
from typing import Optional, Dict, Any

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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
    if host not in LOCAL_HOSTS and not os.getenv("R_LINK_API_TOKEN"):
        raise RuntimeError("Set R_LINK_API_TOKEN before binding to a non-loopback address")
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

        return payload

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


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Dict[str, Any]:
    """Allow an explicit service key, or trusted loopback access when none is set."""
    configured_token = os.getenv("R_LINK_API_TOKEN", "")
    if configured_token:
        if credentials and hmac.compare_digest(credentials.credentials.encode(), configured_token.encode()):
            return {"id": "service-" + hashlib.sha256(configured_token.encode()).hexdigest()[:24]}
        raise HTTPException(401, "Service access key required", headers={"WWW-Authenticate": "Bearer"})

    origin = request.headers.get("origin")
    # Check the peer, Host and browser origin together; a local proxy alone is not authentication.
    if (request.client and is_loopback(request.client.host)
            and request.url.hostname in LOCAL_HOSTS
            and (not origin or origin in allowed_origins() or origin == str(request.base_url).rstrip("/"))
            and (origin or request.headers.get("sec-fetch-site") != "cross-site")):
        return {"id": "local-operator"}
    raise HTTPException(401, "Local access only; configure a service access key for remote use")


# All service operators manage this server; cloud account roles no longer exist.
require_admin = require_auth
