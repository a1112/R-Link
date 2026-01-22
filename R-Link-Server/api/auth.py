"""
认证 API 路由

处理用户登录、登出、会话验证等
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from core.supabase_auth import auth_manager, require_auth, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/session")
async def get_session(user: dict = require_auth):
    """
    获取当前会话信息

    需要认证
    """
    return {
        "user": user,
        "authenticated": True
    }


@router.post("/verify")
async def verify_token(token: str):
    """
    验证 token 是否有效

    Args:
        token: JWT token

    Returns:
        用户信息（如果 token 有效）
    """
    user_data = await auth_manager.verify_token(token)

    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    return {
        "valid": True,
        "user": {
            "id": user_data.get("id"),
            "email": user_data.get("email"),
            "role": user_data.get("role", "authenticated"),
        }
    }


@router.post("/refresh")
async def refresh_session(refresh_token: str):
    """
    刷新会话

    Args:
        refresh_token: 刷新 token

    Returns:
        新的访问 token
    """
    session_data = await auth_manager.refresh_session(refresh_token)

    if session_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    return {
        "access_token": session_data.get("access_token"),
        "refresh_token": session_data.get("refresh_token"),
        "expires_in": session_data.get("expires_in"),
        "token_type": "bearer"
    }


@router.get("/me")
async def get_current_user_info(user: dict = require_auth):
    """
    获取当前用户信息

    需要认证
    """
    return user


@router.post("/logout")
async def logout(user: dict = require_auth):
    """
    登出（前端负责清除 token）

    需要认证
    """
    # Supabase 的 JWT 是无状态的，只需前端清除 token
    # 如果需要强制失效 token，可以使用 Supabase 的 admin API
    return {
        "message": "Logged out successfully"
    }
