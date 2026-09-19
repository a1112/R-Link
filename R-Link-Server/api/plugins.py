"""
插件相关的 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import os
import shutil
import zipfile
import httpx
import tempfile
from urllib.parse import urlsplit
from core.plugin_packages import plugin_path, safe_extract_zip, install_zip, MAX_PACKAGE_BYTES
from pathlib import Path

from core.plugin_manager import PluginManager
from core.plugin_interface import PluginState
from core.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/plugins",
    tags=["plugins"],
    dependencies=[Depends(require_admin)],
)

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


class PluginInstallRequest(BaseModel):
    """插件安装请求"""
    url: Optional[str] = None
    name: Optional[str] = None


class PluginUninstallRequest(BaseModel):
    """插件卸载请求"""
    name: str


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

    info = next(info for info in plugin_manager.get_all_plugins() if info.name == name)
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
            "status": state.status.value if state else "unknown",
            "pid": state.pid if state else None,
            "port": state.port if state else None,
            "uptime": state.uptime if state else 0,
            "memory_usage": state.memory_usage if state else 0,
            "cpu_usage": state.cpu_usage if state else 0,
            "last_error": state.last_error if state else None
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


# ========== 插件安装/卸载 ==========

def _plugins_root() -> Path:
    if not plugin_manager:
        raise HTTPException(503, "Plugin manager not initialized")
    return Path(plugin_manager.plugins_dir).resolve()


@router.post("/install/upload")
async def install_plugin_upload(file: UploadFile = File(...)):
    root = _plugins_root()
    filename = file.filename or ""
    if "/" in filename or "\\" in filename or ":" in filename:
        raise HTTPException(400, "Invalid upload filename")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".zip", ".py"}:
        raise HTTPException(400, "Supported file formats: .zip, .py")
    with tempfile.TemporaryDirectory(prefix="rlink-upload-") as temporary:
        path = Path(temporary) / ("package" + suffix)
        size = 0
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PACKAGE_BYTES:
                    raise HTTPException(413, "Plugin package is too large")
                output.write(chunk)
        if suffix == ".zip":
            name = await _extract_and_install_zip(path, str(root))
        else:
            name = Path(filename).stem
            target = plugin_path(root, name)
            if plugin_manager.is_builtin(name) or target.exists():
                raise HTTPException(409, "Plugin already installed")
            target.mkdir(parents=True)
            shutil.move(str(path), str(target / "__init__.py"))
            await _create_basic_manifest(target, name)
    await _reload_plugin_manager()
    return {"status": "success", "message": f"Plugin {name} installed successfully", "plugin": name}


@router.post("/install/url")
async def install_plugin_from_url(request: PluginInstallRequest):
    root = _plugins_root()
    parsed = urlsplit(request.url or "")
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or not parsed.path.lower().endswith(".zip"):
        raise HTTPException(400, "An HTTP(S) URL to a ZIP package is required")
    with tempfile.TemporaryDirectory(prefix="rlink-download-") as temporary:
        path = Path(temporary) / "package.zip"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("GET", request.url) as response:
                    response.raise_for_status()
                    size = 0
                    with path.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > MAX_PACKAGE_BYTES:
                                raise HTTPException(413, "Plugin package is too large")
                            output.write(chunk)
        except httpx.HTTPError as error:
            raise HTTPException(400, "Failed to download plugin") from error
        name = await _extract_and_install_zip(path, str(root))
    await _reload_plugin_manager()
    return {"status": "success", "message": f"Plugin {name} installed successfully", "plugin": name}


@router.delete("/uninstall")
async def uninstall_plugin(request: PluginUninstallRequest):
    root = _plugins_root()
    target = plugin_path(root, request.name)
    if plugin_manager.is_builtin(request.name):
        raise HTTPException(400, "Cannot uninstall builtin plugin")
    if not target.is_dir():
        raise HTTPException(404, "Plugin not found")
    plugin = plugin_manager.get_plugin(request.name)
    if plugin and not plugin.stop():
        raise HTTPException(409, "Plugin could not be stopped")
    shutil.rmtree(target)
    plugin_manager.plugins.pop(request.name, None)
    return {"status": "success", "message": f"Plugin {request.name} uninstalled successfully"}


@router.post("/reload")
async def reload_plugins():
    """
    重新加载所有插件
    """
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    # 重新加载插件
    await _reload_plugin_manager()

    plugins = plugin_manager.get_all_plugins()
    return {
        "status": "success",
        "message": f"Reloaded {len(plugins)} plugins",
        "plugins": [p.name for p in plugins]
    }


# ========== 辅助函数 ==========

async def _extract_and_install_zip(zip_path: Path, target_dir: str) -> str:
    return install_zip(zip_path, Path(target_dir))


_safe_extract_zip = safe_extract_zip


async def _create_basic_manifest(plugin_dir: Path, plugin_name: str):
    """创建基本的 manifest 文件"""
    import yaml
    manifest_path = plugin_dir / "manifest.yaml"

    manifest = {
        "name": plugin_name,
        "version": "1.0.0",
        "description": f"{plugin_name} plugin",
        "author": "Unknown",
        "entry": "__init__.py",
        "category": "general"
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(manifest, f)


async def _reload_plugin_manager():
    """Reload in place so API, console and lifespan retain the same manager."""
    if plugin_manager:
        plugin_manager.cleanup()
        plugin_manager.plugins.clear()
        plugin_manager._load_plugins()
