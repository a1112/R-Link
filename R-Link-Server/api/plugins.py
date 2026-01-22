"""
插件相关的 API 路由
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import os
import shutil
import zipfile
import httpx
from pathlib import Path

from core.plugin_manager import PluginManager
from core.plugin_interface import PluginState

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

@router.post("/install/upload")
async def install_plugin_upload(file: UploadFile = File(...)):
    """
    通过上传插件包安装插件

    支持的格式：
    - .zip 压缩包（包含 manifest.yaml 或 manifest.json）
    - .py 单文件插件
    - .exe 二进制插件（需要附带 manifest.yaml）
    """
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    # 创建临时目录
    temp_dir = Path("plugins/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 保存上传的文件
        file_path = temp_dir / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 处理不同类型的文件
        if file.filename.endswith(".zip"):
            # 解压 ZIP 文件
            plugin_name = await _extract_and_install_zip(file_path, "plugins")
        elif file.filename.endswith(".py"):
            # 单 Python 文件插件
            plugin_name = file_path.stem
            plugin_dir = Path("plugins") / plugin_name
            plugin_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(file_path, plugin_dir / "__init__.py")
            # 创建基本 manifest
            await _create_basic_manifest(plugin_dir, plugin_name)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Please upload .zip, .py, or .exe with manifest"
            )

        # 重新加载插件
        await _reload_plugin_manager()

        return {
            "status": "success",
            "message": f"Plugin {plugin_name} installed successfully",
            "plugin": plugin_name
        }

    except Exception as e:
        logger.error(f"Plugin installation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 清理临时文件
        if file_path.exists():
            file_path.unlink()


@router.post("/install/url")
async def install_plugin_from_url(request: PluginInstallRequest):
    """
    从 URL 下载并安装插件
    """
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")

    temp_dir = Path("plugins/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 下载文件
        filename = request.url.split("/")[-1].split("?")[0]
        file_path = temp_dir / filename

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(request.url)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                f.write(response.content)

        # 处理下载的文件
        if filename.endswith(".zip"):
            plugin_name = await _extract_and_install_zip(file_path, "plugins")
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format from URL"
            )

        # 重新加载插件
        await _reload_plugin_manager()

        return {
            "status": "success",
            "message": f"Plugin {plugin_name} installed successfully",
            "plugin": plugin_name
        }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to download plugin: {e}")
    except Exception as e:
        logger.error(f"Plugin installation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/uninstall")
async def uninstall_plugin(request: PluginUninstallRequest):
    """
    卸载插件

    注意：内置插件不能卸载
    """
    if not plugin_manager:
        raise HTTPException(status_code=500, detail="Plugin manager not initialized")

    # 检查是否为内置插件
    if plugin_manager.is_builtin(request.name):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot uninstall builtin plugin: {request.name}"
        )

    # 停止插件
    plugin_manager.stop_plugin(request.name)

    # 删除插件目录
    plugin_dir = Path("plugins") / request.name
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)

    # 从管理器中移除
    if request.name in plugin_manager.plugins:
        del plugin_manager.plugins[request.name]

    return {
        "status": "success",
        "message": f"Plugin {request.name} uninstalled successfully"
    }


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
    """解压 ZIP 文件并安装插件"""
    temp_extract = Path(target_dir) / "temp" / "extract"
    temp_extract.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)

    # 查找包含 manifest 的目录
    manifest_path = None
    for root, dirs, files in os.walk(temp_extract):
        if "manifest.yaml" in files or "manifest.json" in files:
            manifest_path = Path(root)
            break

    if not manifest_path:
        raise HTTPException(
            status_code=400,
            detail="No manifest.yaml or manifest.json found in the uploaded package"
        )

    # 获取插件名称
    plugin_name = manifest_path.name if manifest_path != temp_extract else manifest_path.parent.name

    # 移动到目标目录
    target_path = Path(target_dir) / plugin_name
    if target_path.exists():
        shutil.rmtree(target_path)

    shutil.move(str(manifest_path), str(target_path))

    # 清理临时目录
    shutil.rmtree(temp_extract.parent)

    return plugin_name


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
    """重新加载插件管理器"""
    global plugin_manager
    # 重新初始化插件管理器
    from core.plugin_manager import PluginManager
    old_manager = plugin_manager
    plugin_manager = PluginManager(plugins_dir="plugins", builtin_dir="builtin")
    set_plugin_manager(plugin_manager)
    # 清理旧管理器
    if old_manager:
        old_manager.cleanup()
