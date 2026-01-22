"""
WebSSH 插件 - 内置 Python 插件
支持通过 WebSocket 在浏览器中连接 SSH 服务器
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


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


class Plugin:
    """WebSSH 插件主类"""

    def __init__(self, config: Dict[str, Any] = None, plugin_dir: str = None):
        self.config = config or {}
        self.plugin_dir = plugin_dir
        self.status = "running"
        self.manager = get_connection_manager()

    def get_info(self):
        """获取插件信息"""
        return {
            "name": "webssh-plugin",
            "version": "1.0.0",
            "description": "Web SSH 终端插件 - 支持浏览器中通过 SSH 连接远程服务器",
            "author": "R-Link Team",
            "binary_path": __file__,
        }

    def start(self, config: Dict[str, Any] = None) -> bool:
        """启动插件"""
        self.status = "running"
        return True

    def stop(self) -> bool:
        """停止插件"""
        self.status = "stopped"
        return True

    def restart(self) -> bool:
        """重启插件"""
        return True

    def get_status(self):
        """获取插件状态"""
        return {
            "status": self.status,
            "pid": None,
            "port": None,
            "uptime": 0,
            "active_connections": self.manager.get_connection_count(),
        }

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "max_connections": self.config.get("max_connections", 10),
            "connection_timeout": self.config.get("connection_timeout", 30),
            "keepalive_interval": self.config.get("keepalive_interval", 30),
        }

    def set_config(self, config: Dict[str, Any]) -> bool:
        """设置配置"""
        self.config.update(config)
        if "max_connections" in config:
            self.manager.max_connections = config["max_connections"]
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return True

    def get_logs(self, lines: int = 100) -> str:
        """获取日志"""
        return "WebSSH plugin - WebSocket terminal service"

    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Any:
        """执行命令"""
        if command == "list_connections":
            return {"connections": self.manager.list_connections()}

        elif command == "close_connection":
            connection_id = args.get("connection_id") if args else None
            if not connection_id:
                return {"error": "connection_id required"}
            self.manager.close_connection(connection_id)
            return {"success": True, "message": "Connection closed"}

        elif command == "get_connection_info":
            connection_id = args.get("connection_id") if args else None
            if not connection_id:
                return {"error": "connection_id required"}
            conn = self.manager.get_connection(connection_id)
            if not conn:
                return {"error": "Connection not found"}
            return {
                "id": conn.id,
                "host": conn.host,
                "port": conn.port,
                "username": conn.username,
                "status": conn.status.value,
                "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
                "last_activity": conn.last_activity.isoformat() if conn.last_activity else None,
            }

        else:
            return {"error": f"Unknown command: {command}"}


# 插件入口点
plugin = Plugin
