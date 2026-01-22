"""
R-Link-Server 主入口

插件化管理平台的后端服务
"""
import sys
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# 添加项目根目录到 Python 路径，支持直接运行
_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from core.plugin_manager import PluginManager
from core.supabase_auth import auth_manager
from api.plugins import router as plugins_router, set_plugin_manager
from api.system import router as system_router
from api.plugin_sources import router as sources_router
from api.auth import router as auth_router
from api.ssh import router as ssh_router
from api.console import router as console_router, set_plugin_manager as set_console_plugin_manager

# 配置日志
# 创建必要的目录
Path("logs").mkdir(exist_ok=True)
Path("config").mkdir(exist_ok=True)
Path("plugins").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 全局插件管理器
plugin_manager: PluginManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global plugin_manager

    # 启动时初始化
    logger.info("Starting R-Link-Server...")

    # 初始化插件管理器（用户插件 + 内置插件）
    plugin_manager = PluginManager(plugins_dir="plugins", builtin_dir="builtin")
    set_plugin_manager(plugin_manager)
    set_console_plugin_manager(plugin_manager)

    # 打印已加载的插件
    plugins = plugin_manager.get_all_plugins()
    logger.info(f"Loaded {len(plugins)} plugins: {[p.name for p in plugins]}")

    yield

    # 关闭时清理
    logger.info("Shutting down R-Link-Server...")
    if plugin_manager:
        plugin_manager.cleanup()
    await auth_manager.close()


# 创建 FastAPI 应用
app = FastAPI(
    title="R-Link-Server",
    description="R-Link 插件化管理平台后端服务",
    version="0.1.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(plugins_router)
app.include_router(system_router)
app.include_router(sources_router)
app.include_router(ssh_router)
app.include_router(console_router)


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "R-Link-Server",
        "version": "0.1.0",
        "status": "running"
    }


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


def main():
    """主函数"""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式，生产环境设置为 False
        log_level="info"
    )


if __name__ == "__main__":
    main()
