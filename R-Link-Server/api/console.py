"""
Console API
提供 Web 控制台管理接口
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/console", tags=["Console"])

# 全局插件管理器引用
_plugin_manager = None


def set_plugin_manager(plugin_manager):
    """设置插件管理器"""
    global _plugin_manager
    _plugin_manager = plugin_manager


def get_console_plugin():
    """获取控制台插件实例"""
    if _plugin_manager is None:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    # 获取 ttyd-console 插件
    plugin = _plugin_manager.get_plugin("ttyd-console")
    if plugin is None:
        raise HTTPException(status_code=404, detail="Console plugin not found")

    return plugin


class ConsoleConfigRequest(BaseModel):
    """控制台配置请求"""
    command: str = Field("cmd.exe", description="要执行的命令")
    port: int = Field(7681, description="ttyd 监听端口")
    enable_nginx_proxy: bool = Field(True, description="是否启用 nginx 代理")


@router.get("/status")
async def get_console_status():
    """获取控制台状态"""
    plugin = get_console_plugin()
    status = plugin.get_status()
    return status


@router.post("/start")
async def start_console():
    """启动控制台服务"""
    plugin = get_console_plugin()

    # 获取插件实例并执行命令
    if hasattr(plugin, 'instance') and plugin.instance:
        result = plugin.instance.execute_command("start_ttyd")
    else:
        result = {"error": "Plugin instance not available"}

    return result


@router.post("/stop")
async def stop_console():
    """停止控制台服务"""
    plugin = get_console_plugin()

    if hasattr(plugin, 'instance') and plugin.instance:
        result = plugin.instance.execute_command("stop_ttyd")
    else:
        result = {"error": "Plugin instance not available"}

    return result


@router.post("/restart")
async def restart_console():
    """重启控制台服务"""
    plugin = get_console_plugin()

    if hasattr(plugin, 'instance') and plugin.instance:
        result = plugin.instance.execute_command("restart_ttyd")
    else:
        result = {"error": "Plugin instance not available"}

    return result


@router.get("/url")
async def get_console_url():
    """获取控制台访问地址"""
    plugin = get_console_plugin()

    if hasattr(plugin, 'instance') and plugin.instance:
        result = plugin.instance.execute_command("get_url")
    else:
        result = {"error": "Plugin instance not available"}

    return result


@router.post("/config")
async def update_console_config(request: ConsoleConfigRequest):
    """更新控制台配置"""
    plugin = get_console_plugin()

    config = {
        "command": request.command,
        "ttyd_port": request.port,
        "enable_nginx_proxy": request.enable_nginx_proxy,
    }

    if hasattr(plugin, 'instance') and plugin.instance:
        plugin.instance.set_config(config)
        return {"success": True, "config": config}
    else:
        return {"error": "Plugin instance not available"}
