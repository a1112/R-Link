"""
Python Plugin Runner
支持加载和运行 Python 插件（.py/.pyd 文件）
"""
import sys
import os
import json
import logging
import subprocess
import threading
import time
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PythonPluginStatus(Enum):
    """Python 插件状态"""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class PythonPluginInfo:
    """Python 插件信息"""
    name: str
    version: str
    description: str
    author: str
    entry_file: str               # Python 入口文件
    config_template: Dict[str, Any] = None
    default_config: Dict[str, Any] = None
    dependencies: List[str] = None
    category: str = "general"
    builtin: bool = False
    icon: Optional[str] = None
    ui_template: Optional[str] = None

    def __post_init__(self):
        if self.config_template is None:
            self.config_template = {}
        if self.default_config is None:
            self.default_config = {}
        if self.dependencies is None:
            self.dependencies = []


class PythonPlugin:
    """Python 插件运行器"""

    def __init__(self, info: PythonPluginInfo, plugin_dir: str):
        self.info = info
        self.plugin_dir = plugin_dir
        self.status = PythonPluginStatus.UNLOADED
        self.module = None
        self.instance = None
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.config_path = os.path.join(plugin_dir, "config", f"{info.name}.json")
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def load(self) -> bool:
        """加载 Python 插件"""
        try:
            # 添加插件目录到 Python 路径
            plugin_path = Path(self.plugin_dir)
            if str(plugin_path) not in sys.path:
                sys.path.insert(0, str(plugin_path))

            # 动态导入模块
            entry_file = plugin_path / self.info.entry_file
            if not entry_file.exists():
                # 尝试 .pyd 文件
                pyd_file = plugin_path / f"{self.info.entry_file.removesuffix('.py')}.pyd"
                if not pyd_file.exists():
                    raise FileNotFoundError(f"Plugin entry file not found: {entry_file}")

            spec = importlib.util.spec_from_file_location(
                self.info.name.replace("-", "_"),
                str(entry_file)
            )
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

            self.status = PythonPluginStatus.LOADED
            logger.info(f"Python plugin loaded: {self.info.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {self.info.name}: {e}")
            self.status = PythonPluginStatus.ERROR
            return False

    def instantiate(self, config: Dict[str, Any] = None) -> bool:
        """实例化插件"""
        if self.status != PythonPluginStatus.LOADED:
            if not self.load():
                return False

        try:
            # 合并配置
            final_config = self.info.default_config.copy()
            if config:
                final_config.update(config)

            # 获取插件类
            plugin_class = getattr(self.module, "Plugin", None)
            if plugin_class is None:
                raise AttributeError(f"No Plugin class found in {self.info.entry_file}")

            # 创建实例
            self.instance = plugin_class(config=final_config, plugin_dir=self.plugin_dir)
            self.status = PythonPluginStatus.RUNNING
            return True

        except Exception as e:
            logger.error(f"Failed to instantiate plugin {self.info.name}: {e}")
            self.status = PythonPluginStatus.ERROR
            return False

    def start(self, config: Dict[str, Any] = None) -> bool:
        """启动插件"""
        try:
            # 保存配置
            final_config = self.info.default_config.copy()
            if config:
                final_config.update(config)
            self._save_config(final_config)

            # 实例化并启动
            if not self.instantiate(final_config):
                return False

            # 如果插件有 run 方法，在单独线程中运行
            if hasattr(self.instance, 'run') and callable(self.instance.run):
                self.stop_event.clear()
                self.thread = threading.Thread(
                    target=self._run_plugin,
                    daemon=True
                )
                self.thread.start()
            else:
                # 没有 run 方法，认为已启动
                self.status = PythonPluginStatus.RUNNING

            logger.info(f"Python plugin started: {self.info.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to start plugin {self.info.name}: {e}")
            self.status = PythonPluginStatus.ERROR
            return False

    def _run_plugin(self):
        """在单独线程中运行插件"""
        try:
            if hasattr(self.instance, 'run') and callable(self.instance.run):
                # 传递停止事件
                if hasattr(self.instance, 'set_stop_event'):
                    self.instance.set_stop_event(self.stop_event)
                # 执行 run 方法
                result = self.instance.run()
                logger.info(f"Plugin {self.info.name} run() returned: {result}")
        except Exception as e:
            logger.error(f"Plugin {self.info.name} run error: {e}")
        finally:
            self.status = PythonPluginStatus.LOADED

    def stop(self) -> bool:
        """停止插件"""
        try:
            self.stop_event.set()

            # 调用插件的 stop 方法
            if self.instance and hasattr(self.instance, 'stop') and callable(self.instance.stop):
                self.instance.stop()

            # 等待线程结束
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)

            self.status = PythonPluginStatus.LOADED
            logger.info(f"Python plugin stopped: {self.info.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop plugin {self.info.name}: {e}")
            return False

    def restart(self) -> bool:
        """重启插件"""
        config = self.get_config()
        self.stop()
        return self.start(config)

    def get_info(self) -> PythonPluginInfo:
        """获取插件信息"""
        return self.info

    def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        return {
            "status": self.status.value if self.status else "unknown",
            "loaded": self.module is not None,
            "running": self.status == PythonPluginStatus.RUNNING,
            "has_instance": self.instance is not None,
        }

    def get_logs(self, lines: int = 100) -> str:
        """获取插件日志（Python 插件没有进程日志）"""
        return f"Python plugin {self.info.name} has no process logs."

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        return self.info.default_config.copy()

    def set_config(self, config: Dict[str, Any]) -> bool:
        """设置配置"""
        try:
            self._save_config(config)
            if self.instance and hasattr(self.instance, 'set_config'):
                self.instance.set_config(config)
            return True
        except Exception as e:
            logger.error(f"Error setting config: {e}")
            return False

    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Any:
        """执行自定义命令"""
        if not self.instance:
            return {"error": "Plugin not running"}

        try:
            method = getattr(self.instance, command, None)
            if callable(method):
                return method(**(args or {}))
            else:
                return {"error": f"Command {command} not found"}
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            return {"error": str(e)}

    def _save_config(self, config: Dict[str, Any]):
        """保存配置"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def cleanup(self):
        """清理资源"""
        self.stop()
        self.module = None
        self.instance = None


class PythonPluginManager:
    """Python 插件管理器"""

    def __init__(self, plugins_dir: str = "plugins", builtin_dir: str = "builtin"):
        self.plugins_dir = plugins_dir
        self.builtin_dir = builtin_dir
        self.plugins: Dict[str, PythonPlugin] = {}
        self._load_plugins()

    def _load_plugins(self):
        """加载所有 Python 插件"""
        self._load_from_dir(self.plugins_dir, "user")
        self._load_from_dir(self.builtin_dir, "builtin")

    def _load_from_dir(self, dir_path: str, dir_type: str):
        """从目录加载插件"""
        plugins_path = Path(dir_path)
        if not plugins_path.exists():
            return

        for plugin_dir in plugins_path.iterdir():
            if not plugin_dir.is_dir():
                continue

            manifest_file = plugin_dir / "manifest.yaml"
            if not manifest_file.exists():
                manifest_file = plugin_dir / "manifest.json"

            if not manifest_file.exists():
                continue

            try:
                info = self._load_manifest(manifest_file)
                info.builtin = (dir_type == "builtin")

                plugin = PythonPlugin(info, str(plugin_dir))
                self.plugins[info.name] = plugin
                logger.info(f"Loaded Python plugin: {info.name} ({dir_type})")

            except Exception as e:
                logger.error(f"Error loading Python plugin {plugin_dir.name}: {e}")

    def _load_manifest(self, manifest_path: Path) -> PythonPluginInfo:
        """加载插件清单"""
        import yaml
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) if manifest_path.suffix in ['.yaml', '.yml'] else json.load(f)
        return PythonPluginInfo(**data)

    def get_all_plugins(self) -> List[PythonPluginInfo]:
        """获取所有插件信息"""
        return [plugin.info for plugin in self.plugins.values()]

    def get_plugin(self, name: str) -> Optional[PythonPlugin]:
        """获取插件"""
        return self.plugins.get(name)

    def reload_plugin(self, name: str) -> bool:
        """重新加载插件"""
        plugin = self.plugins.get(name)
        if not plugin:
            return False

        try:
            # 卸载模块
            if plugin.module:
                module_name = plugin.info.name.replace("-", "_")
                if module_name in sys.modules:
                    del sys.modules[module_name]
                    # 同时删除子模块
                    to_delete = [k for k in sys.modules if k.startswith(module_name + ".")]
                    for k in to_delete:
                        del sys.modules[k]

            # 重新加载
            return plugin.load()
        except Exception as e:
            logger.error(f"Failed to reload plugin {name}: {e}")
            return False

    def get_plugin_instance(self, name: str) -> Optional[Any]:
        """获取插件实例"""
        plugin = self.plugins.get(name)
        return plugin.instance if plugin else None

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """获取所有插件状态"""
        return {
            name: plugin.get_status()
            for name, plugin in self.plugins.items()
        }
