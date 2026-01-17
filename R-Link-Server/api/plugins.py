"""
插件相关的 API 路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging

from ..core.plugin_manager import PluginManager
from ..core.plugin_interface import PluginState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

# 全局插件管理器实例（在 main.py 中初始化）
plugin_manager: Optional[PluginManager] = None


def set_plugin_manager(manager: PluginManager):
    """设置插件管理器实例"""
    global plugin_manager
    plugin_manager = manager


# ========== 请求/响应模型 ==========

class PluginConfigRequest(BaseModel):
    """插件配置请求"""
    config: Dict[str, Any]


class PluginStartRequest(BaseModel):
    """插件启动请求"""
    config: Optional[Dict[str, Any]] = None


class PluginInfoResponse(BaseModel):
    """插件信息响应"""
    name: str
    version: str
    description: str
    author: str
    binary_path: str
    config_path: Optional[str] = None
    icon: Optional[str] = None


class PluginStatusResponse(BaseModel):
    """插件状态响应"""
    status: str
    pid: Optional[int] = None
    port: Optional[int] = None
    uptime: float = 0
    memory_usage: float = 0
    cpu_usage: float = 0
    last_error: Optional[str] = None


# ========== API 路由 ==========

@router.get("/", response_model=List[PluginInfoResponse])
async def list_plugins():
    """获取所有插件列表"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    plugins = plugin_manager.get_all_plugins()
    return [
        PluginInfoResponse(
            name=p.name,
            version=p.version,
            description=p.description,
            author=p.author,
            binary_path=p.binary_path,
            config_path=p.config_path,
            icon=p.icon
        )
        for p in plugins
    ]


@router.get("/{name}", response_model=PluginInfoResponse)
async def get_plugin(name: str):
    """获取指定插件信息"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    plugin = plugin_manager.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")

    info = plugin.get_info()
    return PluginInfoResponse(
        name=info.name,
        version=info.version,
        description=info.description,
        author=info.author,
        binary_path=info.binary_path,
        config_path=info.config_path,
        icon=info.icon
    )


@router.post("/{name}/start")
async def start_plugin(name: str, request: PluginStartRequest = None):
    """启动插件"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    config = request.config if request else None
    success = plugin_manager.start_plugin(name, config)

    if success:
        return {"status": "success", "message": f"Plugin {name} started"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start plugin {name}")


@router.post("/{name}/stop")
async def stop_plugin(name: str):
    """停止插件"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    success = plugin_manager.stop_plugin(name)

    if success:
        return {"status": "success", "message": f"Plugin {name} stopped"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop plugin {name}")


@router.post("/{name}/restart")
async def restart_plugin(name: str):
    """重启插件"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    success = plugin_manager.restart_plugin(name)

    if success:
        return {"status": "success", "message": f"Plugin {name} restarted"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to restart plugin {name}")


@router.get("/{name}/status", response_model=PluginStatusResponse)
async def get_plugin_status(name: str):
    """获取插件状态"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    state = plugin_manager.get_plugin_status(name)
    if not state:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")

    return PluginStatusResponse(
        status=state.status.value,
        pid=state.pid,
        port=state.port,
        uptime=state.uptime,
        memory_usage=state.memory_usage,
        cpu_usage=state.cpu_usage,
        last_error=state.last_error
    )


@router.get("/status/all")
async def get_all_plugin_status():
    """获取所有插件状态"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    statuses = plugin_manager.get_all_statuses()

    return {
        name: {
            "status": state.status.value,
            "pid": state.pid,
            "port": state.port,
            "uptime": state.uptime,
            "memory_usage": state.memory_usage,
            "cpu_usage": state.cpu_usage,
            "last_error": state.last_error
        }
        for name, state in statuses.items()
    }


@router.get("/{name}/config")
async def get_plugin_config(name: str):
    """获取插件配置"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    config = plugin_manager.get_plugin_config(name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")

    return config


@router.put("/{name}/config")
async def set_plugin_config(name: str, request: PluginConfigRequest):
    """设置插件配置"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    success = plugin_manager.set_plugin_config(name, request.config)

    if success:
        return {"status": "success", "message": f"Plugin {name} config updated"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to update plugin {name} config")


@router.get("/{name}/logs")
async def get_plugin_logs(name: str, lines: int = 100):
    """获取插件日志"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    logs = plugin_manager.get_plugin_logs(name, lines)

    return {
        "plugin": name,
        "lines": lines,
        "logs": logs
    }


@router.get("/{name}/health")
async def check_plugin_health(name: str):
    """检查插件健康状态"""
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    plugin = plugin_manager.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")

    is_healthy = plugin.health_check()

    return {
        "plugin": name,
        "healthy": is_healthy
    }
