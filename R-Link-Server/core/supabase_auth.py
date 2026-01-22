"""
Supabase 认证模块

处理用户认证和权限验证
"""
import os
import httpx
import logging
from typing import Optional, Dict, Any
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# 从环境变量读取 Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# 安全认证方案
security = HTTPBearer(auto_error=False)


class SupabaseAuth:
    """Supabase 认证管理器"""

    def __init__(self):
        self.supabase_url = SUPABASE_URL
        self.anon_key = SUPABASE_ANON_KEY
        self.service_key = SUPABASE_SERVICE_ROLE_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()

    def _get_headers(self, use_service_key: bool = False) -> Dict[str, str]:
        """获取请求头"""
        api_key = self.service_key if use_service_key else self.anon_key
        return {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证用户 token

        Args:
            token: JWT token

        Returns:
            用户信息，验证失败返回 None
        """
        if not token:
            return None

        try:
            response = await self.client.get(
                f"{self.supabase_url}/auth/v1/user",
                headers={
                    "apikey": self.anon_key,
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None

    async def get_user(self, token: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        user_data = await self.verify_token(token)
        if user_data:
            return {
                "id": user_data.get("id"),
                "email": user_data.get("email"),
                "role": user_data.get("role", "authenticated"),
                "aud": user_data.get("aud"),
            }
        return None

    async def refresh_session(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """刷新会话"""
        try:
            response = await self.client.post(
                f"{self.supabase_url}/auth/v1/token?grant_type=refresh_token",
                headers=self._get_headers(),
                json={"refresh_token": refresh_token}
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            logger.error(f"Session refresh error: {e}")
            return None


# 全局认证实例
auth_manager = SupabaseAuth()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[Dict[str, Any]]:
    """
    获取当前登录用户

    用于依赖注入，可选认证（允许匿名访问）
    """
    if credentials is None:
        return None

    token = credentials.credentials
    user = await auth_manager.get_user(token)
    return user


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """
    要求用户必须登录

    用于依赖注入，必须认证
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user = await auth_manager.get_user(token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_admin(
    user: Dict[str, Any] = Security(require_auth)
) -> Dict[str, Any]:
    """
    要求管理员权限

    用于依赖注入，需要管理员角色
    """
    # TODO: 从数据库获取用户角色
    # 暂时简化处理，所有认证用户都是管理员
    return user
