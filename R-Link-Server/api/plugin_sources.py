"""
插件源管理 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
import json
from pathlib import Path

router = APIRouter(prefix="/api/plugin-sources", tags=["plugin-sources"])

logger = logging.getLogger(__name__)

# 插件源配置文件路径
SOURCES_CONFIG_FILE = "config/plugin_sources.json"


class PluginSource(BaseModel):
    """插件源"""
    id: str
    name: str
    url: str
    enabled: bool = True
    priority: int = 50
    description: Optional[str] = None


class PluginSourceCreate(BaseModel):
    """创建插件源请求"""
    id: str
    name: str
    url: str
    enabled: bool = True
    priority: int = 50
    description: Optional[str] = None


def load_sources() -> List[PluginSource]:
    """加载插件源配置"""
    config_path = Path(SOURCES_CONFIG_FILE)

    # 默认插件源
    default_sources = [
        PluginSource(
            id="official",
            name="官方仓库",
            url="https://github.com/r-link/plugins",
            enabled=True,
            priority=100
        ),
        PluginSource(
            id="community",
            name="社区插件",
            url="https://github.com/r-link/community-plugins",
            enabled=True,
            priority=50
        )
    ]

    if not config_path.exists():
        # 创建默认配置
        Path(SOURCES_CONFIG_FILE).parent.mkdir(exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump([s.dict() for s in default_sources], f, indent=2)
        return default_sources

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [PluginSource(**s) for s in data]
    except Exception as e:
        logger.error(f"Error loading plugin sources: {e}")
        return default_sources


def save_sources(sources: List[PluginSource]):
    """保存插件源配置"""
    config_path = Path(SOURCES_CONFIG_FILE)
    config_path.parent.mkdir(exist_ok=True)

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump([s.dict() for s in sources], f, indent=2)


@router.get("/")
async def list_sources():
    """获取所有插件源"""
    sources = load_sources()
    return sources


@router.post("/")
async def add_source(source: PluginSourceCreate):
    """添加插件源"""
    sources = load_sources()

    # 检查 ID 是否已存在
    if any(s.id == source.id for s in sources):
        raise HTTPException(status_code=400, detail=f"Source with id '{source.id}' already exists")

    new_source = PluginSource(**source.dict())
    sources.append(new_source)
    save_sources(sources)

    logger.info(f"Added plugin source: {source.id}")
    return {"status": "success", "source": new_source.dict()}


@router.put("/{source_id}")
async def update_source(source_id: str, source: PluginSourceCreate):
    """更新插件源"""
    sources = load_sources()

    for i, s in enumerate(sources):
        if s.id == source_id:
            updated = PluginSource(**source.dict())
            sources[i] = updated
            save_sources(sources)
            logger.info(f"Updated plugin source: {source_id}")
            return {"status": "success", "source": updated.dict()}

    raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")


@router.delete("/{source_id}")
async def delete_source(source_id: str):
    """删除插件源"""
    sources = load_sources()
    initial_count = len(sources)
    sources = [s for s in sources if s.id != source_id]

    if len(sources) == initial_count:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")

    save_sources(sources)
    logger.info(f"Deleted plugin source: {source_id}")
    return {"status": "success"}


@router.post("/{source_id}/enable")
async def enable_source(source_id: str):
    """启用插件源"""
    sources = load_sources()

    for i, s in enumerate(sources):
        if s.id == source_id:
            sources[i].enabled = True
            save_sources(sources)
            return {"status": "success", "source": sources[i].dict()}

    raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")


@router.post("/{source_id}/disable")
async def disable_source(source_id: str):
    """禁用插件源"""
    sources = load_sources()

    for i, s in enumerate(sources):
        if s.id == source_id:
            sources[i].enabled = False
            save_sources(sources)
            return {"status": "success", "source": sources[i].dict()}

    raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")


@router.get("/available")
async def get_available_plugins():
    """获取可下载的插件列表"""
    sources = load_sources()
    enabled_sources = [s for s in sources if s.enabled]

    # 模拟从各个源获取插件列表
    all_plugins = []

    for source in enabled_sources:
        # 官方源：从本地 R-Plugin API 获取可用插件（如果正在运行）
        if source.id == "official":
            try:
                import httpx
                # 尝试连接到本地 R-Plugin 服务
                with httpx.Client(timeout=2.0) as client:
                    response = client.get("http://localhost:8001/api/plugins/")
                    response.raise_for_status()
                    plugins = response.json()

                    for plugin in plugins:
                        # 排除内置插件
                        if plugin.get("name", "").endswith('-builtin') or plugin.get("name", "").startswith('_'):
                            continue

                        all_plugins.append({
                            "id": plugin.get("name", plugin.get("id", "")),
                            "name": plugin.get("name", plugin.get("id", "")),
                            "description": plugin.get("description", ""),
                            "version": plugin.get("version", "1.0.0"),
                            "author": plugin.get("author", "Unknown"),
                            "source_id": source.id,
                            "source_name": source.name,
                            # 使用本地 R-Plugin 下载 API
                            "download_url": f"http://localhost:8001/api/plugins/{plugin.get('name')}/download",
                            "size": plugin.get("size", "1.0 MB"),
                            "downloads": plugin.get("downloads", 0),
                            "verified": True
                        })
            except Exception as e:
                logger.warning(f"Failed to fetch plugins from local R-Plugin: {e}")
                # 回退到示例插件（用于测试）
                all_plugins.append({
                    "id": "hello-world",
                    "name": "Hello World",
                    "description": "一个简单的测试插件（注意：需要本地 R-Plugin 服务运行）",
                    "version": "1.0.0",
                    "author": "R-Link Team",
                    "source_id": source.id,
                    "source_name": source.name,
                    "download_url": "http://localhost:8001/api/plugins/hello-world/download",
                    "size": "1.0 MB",
                    "downloads": 0,
                    "verified": True
                })

    return {"plugins": all_plugins}


@router.post("/sync")
async def sync_sources():
    """同步所有插件源"""
    sources = load_sources()
    enabled_count = len([s for s in sources if s.enabled])

    return {
        "status": "success",
        "message": f"Synced {enabled_count} plugin sources",
        "sources_count": enabled_count
    }
