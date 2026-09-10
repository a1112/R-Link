"""Shared WebSSH connection registry for API and dynamically loaded plugins."""
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class SSHConnectionStatus(Enum):
    """SSH 连接状态"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class SSHConnection:
    """SSH 连接信息"""
    id: str
    host: str
    port: int
    username: str
    status: SSHConnectionStatus = SSHConnectionStatus.DISCONNECTED
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    error: Optional[str] = None


class SSHConnectionManager:
    """SSH 连接管理器"""

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections: Dict[str, SSHConnection] = {}
        self.websockets: Dict[str, Any] = {}

    def create_connection(
        self,
        connection_id: str,
        host: str,
        port: int,
        username: str,
    ) -> SSHConnection:
        """创建新连接记录"""
        conn = SSHConnection(
            id=connection_id,
            host=host,
            port=port,
            username=username,
            status=SSHConnectionStatus.CONNECTING,
        )
        self.connections[connection_id] = conn
        return conn

    def get_connection(self, connection_id: str) -> Optional[SSHConnection]:
        """获取连接"""
        return self.connections.get(connection_id)

    def update_connection_status(
        self,
        connection_id: str,
        status: SSHConnectionStatus,
        error: Optional[str] = None,
    ):
        """更新连接状态"""
        conn = self.connections.get(connection_id)
        if conn:
            conn.status = status
            conn.error = error
            if status == SSHConnectionStatus.CONNECTED:
                conn.connected_at = datetime.now()
            conn.last_activity = datetime.now()

    def close_connection(self, connection_id: str):
        """关闭连接"""
        if connection_id in self.connections:
            del self.connections[connection_id]
        if connection_id in self.websockets:
            del self.websockets[connection_id]

    def list_connections(self) -> list:
        """列出所有连接"""
        return [
            {
                "id": conn.id,
                "host": conn.host,
                "port": conn.port,
                "username": conn.username,
                "status": conn.status.value,
                "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
                "last_activity": conn.last_activity.isoformat() if conn.last_activity else None,
            }
            for conn in self.connections.values()
        ]

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.connections)


# 全局连接管理器实例
_connection_manager: Optional[SSHConnectionManager] = None


def get_connection_manager() -> SSHConnectionManager:
    """获取全局连接管理器"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = SSHConnectionManager()
    return _connection_manager
