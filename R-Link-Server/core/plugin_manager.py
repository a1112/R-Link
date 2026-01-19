"""
Plugin Manager

Responsible for plugin discovery, loading, and management
Supports both binary plugins (exe) and Python plugins (.py)
"""
import os
import json
import yaml
import logging
import importlib.util
import sys
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path

from .plugin_interface import PluginInfo, PluginState, PluginStatus, IPlugin
from .process_pool import ProcessPool
from .python_plugin import PythonPlugin, PythonPluginInfo, PythonPluginManager

logger = logging.getLogger(__name__)


@dataclass
class PluginManifest:
    """Plugin Manifest"""
    name: str
    version: str
    description: str
    author: str
    binary: str  # For binary plugins
    config_template: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    commands: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    icon: Optional[str] = None
    category: str = "general"
    builtin: bool = False
    ui_template: Optional[str] = None


class BinaryPlugin:
    """Binary Plugin Wrapper"""

    def __init__(
        self,
        manifest: PluginManifest,
        plugin_dir: str,
        process_pool: ProcessPool
    ):
        self.manifest = manifest
        self.plugin_dir = plugin_dir
        self.process_pool = process_pool
        self.config_path = os.path.join(plugin_dir, "config", f"{manifest.name}.json")
        self.binary_path = os.path.join(plugin_dir, manifest.binary)
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure config directory exists"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def get_info(self) -> PluginInfo:
        """Get plugin info"""
        return PluginInfo(
            name=self.manifest.name,
            version=self.manifest.version,
            description=self.manifest.description,
            author=self.manifest.author,
            binary_path=self.binary_path,
            config_path=self.config_path,
            icon=self.manifest.icon
        )

    def start(self, config: Dict[str, Any] = None) -> bool:
        """Start plugin"""
        final_config = self.manifest.default_config.copy()
        if config:
            final_config.update(config)
        self._save_config(final_config)
        args = self._build_args(final_config)
        env = self._build_env(final_config)
        return self.process_pool.start_process(
            self.manifest.name,
            self.binary_path,
            args=args,
            env=env,
            working_dir=self.plugin_dir
        )

    def stop(self) -> bool:
        """Stop plugin"""
        return self.process_pool.stop_process(self.manifest.name)

    def restart(self) -> bool:
        """Restart plugin"""
        return self.process_pool.restart_process(self.manifest.name)

    def get_status(self) -> PluginState:
        """Get status"""
        return self.process_pool.get_process_state(self.manifest.name)

    def get_config(self) -> Dict[str, Any]:
        """Get config"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        return self.manifest.default_config.copy()

    def set_config(self, config: Dict[str, Any]) -> bool:
        """Set config"""
        try:
            self._save_config(config)
            state = self.get_status()
            if state.status == PluginStatus.RUNNING:
                return self.restart()
            return True
        except Exception as e:
            logger.error(f"Error setting config: {e}")
            return False

    def health_check(self) -> bool:
        """Health check"""
        state = self.get_status()
        return state.status == PluginStatus.RUNNING

    def get_logs(self, lines: int = 100) -> str:
        """Get logs"""
        return self.process_pool.get_process_logs(self.manifest.name, lines)

    def _save_config(self, config: Dict[str, Any]):
        """Save config"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

    def _build_args(self, config: Dict[str, Any]) -> List[str]:
        """Build command line args from config"""
        args = []
        if 'args' in config:
            args.extend(config['args'])
        if os.path.exists(self.config_path):
            args.extend(['-c', self.config_path])
        return args

    def _build_env(self, config: Dict[str, Any]) -> Dict[str, str]:
        """Build environment variables from config"""
        env = {}
        if 'env' in config:
            env.update(config['env'])
        return env


class PluginManager:
    """Plugin Manager - 支持二进制插件和 Python 插件"""

    def __init__(self, plugins_dir: str = "plugins", builtin_dir: str = "builtin"):
        self.plugins_dir = plugins_dir
        self.builtin_dir = builtin_dir
        self.plugins: Dict[str, Union[BinaryPlugin, PythonPlugin]] = {}
        self.process_pool = ProcessPool()
        self.python_plugin_manager = PythonPluginManager(plugins_dir, builtin_dir)
        self._load_plugins()

    def _load_plugins(self):
        """加载所有插件（二进制 + Python）"""
        # 加载二进制插件
        self._load_binary_plugins()
        # 加载 Python 插件
        self._load_python_plugins()

    def _load_binary_plugins(self):
        """加载二进制插件"""
        self._load_from_dir(self.plugins_dir, "user", "binary")
        self._load_from_dir(self.builtin_dir, "builtin", "binary")

    def _load_python_plugins(self):
        """加载 Python 插件"""
        self._load_from_dir(self.plugins_dir, "user", "python")
        self._load_from_dir(self.builtin_dir, "builtin", "python")

    def _load_from_dir(self, dir_path: str, dir_type: str, plugin_type: str = "binary"):
        """
        从目录加载插件

        Args:
            dir_path: 插件目录路径
            dir_type: 目录类型 (user/builtin)
            plugin_type: 插件类型 (binary/python)
        """
        plugins_path = Path(dir_path)

        if not plugins_path.exists():
            if dir_type == "user":
                logger.info(f"Creating plugins directory: {dir_path}")
                plugins_path.mkdir(exist_ok=True)
            return

        if not plugins_path.is_dir():
            logger.warning(f"Path {dir_path} is not a directory")
            return

        for plugin_dir in plugins_path.iterdir():
            if not plugin_dir.is_dir():
                continue

            # Python 插件可能有单独的目录
            if plugin_type == "python" or (plugin_type == "binary" and not self._has_binary_plugin(plugin_dir)):
                self._load_python_plugin_from_dir(plugin_dir, dir_type)
            else:
                self._load_binary_plugin_from_dir(plugin_dir, dir_type)

    def _has_binary_plugin(self, plugin_dir: Path) -> bool:
        """检查目录中是否包含二进制文件"""
        # 检查是否有 manifest.yaml/json 或 .exe 文件
        has_manifest = (plugin_dir / "manifest.yaml").exists() or (plugin_dir / "manifest.json").exists()
        has_binary = any(
            f.suffix in [".exe", ""] for f in plugin_dir.iterdir()
        )
        # 检查是否有 .py 文件
        has_python = any(f.suffix == ".py" for f in plugin_dir.iterdir() if f.is_file())

        return has_manifest and (has_binary or not has_python)

    def _load_binary_plugin_from_dir(self, plugin_dir: Path, dir_type: str):
        """从目录加载二进制插件"""
        manifest_file = plugin_dir / "manifest.yaml"
        if not manifest_file.exists():
            manifest_file = plugin_dir / "manifest.json"

        if not manifest_file.exists():
            logger.warning(f"No manifest found in {plugin_dir.name}")
            return

        try:
            manifest = self._load_manifest(manifest_file)
            manifest.builtin = (dir_type == "builtin")

            plugin = BinaryPlugin(
                manifest=manifest,
                plugin_dir=str(plugin_dir),
                process_pool=self.process_pool
            )
            self.plugins[manifest.name] = plugin
            logger.info(f"Loaded {dir_type} binary plugin: {manifest.name} v{manifest.version}")

        except Exception as e:
            logger.error(f"Error loading {dir_type} binary plugin {plugin_dir.name}: {e}")

    def _load_python_plugin_from_dir(self, plugin_dir: Path, dir_type: str):
        """从目录加载 Python 插件"""
        # 首先尝试加载 manifest
        manifest_file = plugin_dir / "manifest.yaml"
        if manifest_file.exists():
            try:
                import yaml
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                data["builtin"] = (dir_type == "builtin")
                info = PythonPluginInfo(**data)

                plugin = PythonPlugin(info, str(plugin_dir))
                self.plugins[info.name] = plugin
                logger.info(f"Loaded {dir_type} Python plugin: {info.name}")
                return

            except Exception as e:
                logger.error(f"Error loading Python plugin manifest from {plugin_dir.name}: {e}")

        # 如果没有 manifest，尝试自动检测
        py_files = list(plugin_dir.glob("*.py"))
        if py_files:
            self._load_python_plugin_without_manifest(plugin_dir, py_files[0], dir_type)
        else:
            # 检查是否有 __init__.py
            init_file = plugin_dir / "__init__.py"
            if init_file.exists():
                self._load_python_package_plugin(plugin_dir, dir_type)
            else:
                logger.warning(f"No valid Python plugin found in {plugin_dir.name}")

    def _load_python_plugin_without_manifest(self, plugin_dir: Path, entry_file: Path, dir_type: str):
        """加载没有 manifest 的 Python 插件"""
        name = plugin_dir.name
        entry_file = entry_file.name

        info = PythonPluginInfo(
            name=name,
            version="1.0.0",
            description=f"{name} Python plugin",
            author="R-Link",
            entry_file=entry_file.name,
            category="general",
            builtin=(dir_type == "builtin")
        )

        plugin = PythonPlugin(info, str(plugin_dir))
        self.plugins[info.name] = plugin
        logger.info(f"Loaded {dir_type} Python plugin (no manifest): {info.name}")

    def _load_python_package_plugin(self, plugin_dir: Path, dir_type: str):
        """加载 Python 包插件"""
        name = plugin_dir.name

        info = PythonPluginInfo(
            name=name,
            version="1.0.0",
            description=f"{name} Python package plugin",
            author="R-Link",
            entry_file="__init__.py",
            category="general",
            builtin=(dir_type == "builtin")
        )

        plugin = PythonPlugin(info, str(plugin_dir))
        self.plugins[info.name] = plugin
        logger.info(f"Loaded {dir_type} Python package plugin: {info.name}")

    def get_all_plugins(self) -> List[PluginInfo]:
        """Get all plugin info"""
        result = []
        for plugin in self.plugins.values():
            if isinstance(plugin, BinaryPlugin):
                result.append(plugin.get_info())
            elif isinstance(plugin, PythonPlugin):
                result.append(plugin.get_info())
        return result

    def get_plugin(self, name: str) -> Optional[Union[BinaryPlugin, PythonPlugin]]:
        """获取指定插件"""
        return self.plugins.get(name)

    def is_builtin(self, name: str) -> bool:
        """检查是否为内置插件"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False
        if isinstance(plugin, BinaryPlugin):
            return plugin.manifest.builtin
        elif isinstance(plugin, PythonPlugin):
            return plugin.info.builtin
        return False

    def get_builtin_plugins(self) -> List[str]:
        """获取所有内置插件名称"""
        builtin = []
        for name, plugin in self.plugins.items():
            if isinstance(plugin, BinaryPlugin):
                if plugin.manifest.builtin:
                    builtin.append(name)
            elif isinstance(plugin, PythonPlugin):
                if plugin.info.builtin:
                    builtin.append(name)
        return builtin

    def get_user_plugins(self) -> List[str]:
        """获取所有用户插件名称"""
        user = []
        for name, plugin in self.plugins.items():
            if isinstance(plugin, BinaryPlugin):
                if not plugin.manifest.builtin:
                    user.append(name)
            elif isinstance(plugin, PythonPlugin):
                if not plugin.info.builtin:
                    user.append(name)
        return user

    def start_plugin(self, name: str, config: Dict[str, Any] = None) -> bool:
        """启动插件"""
        plugin = self.get_plugin(name)
        if not plugin:
            logger.error(f"Plugin {name} not found")
            return False

        if isinstance(plugin, PythonPlugin):
            return plugin.start(config)
        else:
            return plugin.start(config)

    def stop_plugin(self, name: str) -> bool:
        """停止插件（内置插件不能停止）"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False

        if isinstance(plugin, PythonPlugin):
            return plugin.stop()
        elif isinstance(plugin, BinaryPlugin):
            if plugin.manifest.builtin:
                logger.warning(f"Cannot stop builtin plugin: {name}")
                return False
            return plugin.stop()
        else:
            return False

    def restart_plugin(self, name: str) -> bool:
        """重启插件"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False
        return plugin.restart()

    def get_plugin_status(self, name: str) -> Optional[PluginState]:
        """获取插件状态"""
        plugin = self.get_plugin(name)
        if not plugin:
            return None

        if isinstance(plugin, PythonPlugin):
            status = plugin.get_status()
            # 转换为 PluginState
            return PluginState(
                status=PluginStatus.STOPPED if status["status"] == "loaded" else PluginStatus.RUNNING,
                pid=status.get("pid"),
                port=status.get("port"),
                uptime=status.get("uptime", 0),
                memory_usage=status.get("memory_usage", 0),
                cpu_usage=status.get("cpu_usage", 0),
                last_error=status.get("last_error")
            )
        else:
            return plugin.get_status()

    def get_all_statuses(self) -> Dict[str, PluginState]:
        """获取所有插件状态"""
        return {
            name: plugin.get_status()
            for name, plugin in self.plugins.items()
        }

    def get_plugin_config(self, name: str) -> Optional[Dict[str, Any]]:
        """获取插件配置"""
        plugin = self.get_plugin(name)
        if not plugin:
            return None
        return plugin.get_config()

    def set_plugin_config(self, name: str, config: Dict[str, Any]) -> bool:
        """设置插件配置"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False
        return plugin.set_config(config)

    def get_plugin_logs(self, name: str, lines: int = 100) -> str:
        """获取插件日志"""
        plugin = self.get_plugin(name)
        if not plugin:
            return ""
        return plugin.get_logs(lines)

    def execute_command(self, name: str, command: str, args: Dict[str, Any] = None) -> Any:
        """执行插件命令"""
        plugin = self.get_plugin(name)
        if not plugin:
            return {"error": "Plugin not found"}

        if isinstance(plugin, PythonPlugin):
            return plugin.execute_command(command, args)
        else:
            # 二进制插件不支持自定义命令
            return {"error": "Command not supported by binary plugins"}

    def cleanup(self):
        """清理所有插件"""
        self.process_pool.cleanup()

    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        """加载插件清单"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            if manifest_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        return PluginManifest(**data)
