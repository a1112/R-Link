"""SSH ticket exchange for authorized service operators."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.auth import access_manager, require_auth

router = APIRouter(prefix="/api/auth", tags=["service-access"])


class WebSocketTokenResponse(BaseModel):
    token: str
    scope: str
    expires_in: int


@router.post("/ws-token", response_model=WebSocketTokenResponse)
async def issue_websocket_token(user: dict = Depends(require_auth)):
    token = await access_manager.issue_websocket_token(user, scope="ssh", ttl_seconds=60)
    return WebSocketTokenResponse(token=token, scope="ssh", expires_in=60)
