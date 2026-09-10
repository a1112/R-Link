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


from core.webssh_connections import (
    SSHConnection, SSHConnectionStatus, SSHConnectionManager, get_connection_manager,
)


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
