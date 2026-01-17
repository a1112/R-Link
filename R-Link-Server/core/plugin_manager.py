"""
插件管理器

负责插件的发现、加载、管理
"""
import os
import json
import yaml
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

from .plugin_interface import PluginInfo, PluginState, PluginStatus, IPlugin
from .process_pool import ProcessPool

logger = logging.getLogger(__name__)


@dataclass
class PluginManifest:
    """插件清单"""
    name: str
    version: str
    description: str
    author: str
    binary: str                    # 二进制文件名
    config_template: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    commands: Dict[str, str] = field(default_factory=dict)  # 支持的命令
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他插件
    icon: Optional[str] = None
    category: str = "general"      # 分类: network, storage, remote, etc.


class BinaryPlugin:
    """二进制插件包装器"""

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
        """确保配置目录存在"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def get_info(self) -> PluginInfo:
        """获取插件信息"""
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
        """启动插件"""
        # 合并配置
        final_config = self.manifest.default_config.copy()
        if config:
            final_config.update(config)

        # 保存配置
        self._save_config(final_config)

        # 准备启动参数
        args = self._build_args(final_config)

        # 准备环境变量
        env = self._build_env(final_config)

        return self.process_pool.start_process(
            self.manifest.name,
            self.binary_path,
            args=args,
            env=env,
            working_dir=self.plugin_dir
        )

    def stop(self) -> bool:
        """停止插件"""
        return self.process_pool.stop_process(self.manifest.name)

    def restart(self) -> bool:
        """重启插件"""
        return self.process_pool.restart_process(self.manifest.name)

    def get_status(self) -> PluginState:
        """获取状态"""
        return self.process_pool.get_process_state(self.manifest.name)

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        return self.manifest.default_config.copy()

    def set_config(self, config: Dict[str, Any]) -> bool:
        """设置配置"""
        try:
            self._save_config(config)

            # 如果插件正在运行，重启以应用配置
            state = self.get_status()
            if state.status == PluginStatus.RUNNING:
                return self.restart()

            return True
        except Exception as e:
            logger.error(f"Error setting config: {e}")
            return False

    def health_check(self) -> bool:
        """健康检查"""
        state = self.get_status()
        return state.status == PluginStatus.RUNNING

    def get_logs(self, lines: int = 100) -> str:
        """获取日志"""
        return self.process_pool.get_process_logs(self.manifest.name, lines)

    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Any:
        """执行自定义命令"""
        if command not in self.manifest.commands:
            raise ValueError(f"Unknown command: {command}")

        # 这里可以实现具体的命令执行逻辑
        # 对于二进制插件，可能需要通过 IPC 或 HTTP API
        return {"status": "not_implemented"}

    def _save_config(self, config: Dict[str, Any]):
        """保存配置"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def _build_args(self, config: Dict[str, Any]) -> List[str]:
        """根据配置构建命令行参数"""
        args = []

        # 从配置中获取命令行参数
        if 'args' in config:
            args.extend(config['args'])

        # 如果有配置文件，添加配置文件路径
        if os.path.exists(self.config_path):
            args.extend(['-c', self.config_path])

        return args

    def _build_env(self, config: Dict[str, Any]) -> Dict[str, str]:
        """根据配置构建环境变量"""
        env = {}

        # 从配置中获取环境变量
        if 'env' in config:
            env.update(config['env'])

        return env


class PluginManager:
    """插件管理器"""

    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, BinaryPlugin] = {}
        self.process_pool = ProcessPool()
        self._load_plugins()

    def _load_plugins(self):
        """加载所有插件"""
        plugins_path = Path(self.plugins_dir)

        if not plugins_path.exists():
            logger.warning(f"Plugins directory {self.plugins_dir} does not exist")
            return

        # 遍历插件目录
        for plugin_dir in plugins_path.iterdir():
            if not plugin_dir.is_dir():
                continue

            manifest_file = plugin_dir / "manifest.yaml"
            if not manifest_file.exists():
                manifest_file = plugin_dir / "manifest.json"

            if not manifest_file.exists():
                logger.warning(f"No manifest found for plugin {plugin_dir.name}")
                continue

            try:
                manifest = self._load_manifest(manifest_file)
                plugin = BinaryPlugin(
                    manifest=manifest,
                    plugin_dir=str(plugin_dir),
                    process_pool=self.process_pool
                )
                self.plugins[manifest.name] = plugin
                logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")

            except Exception as e:
                logger.error(f"Error loading plugin {plugin_dir.name}: {e}")

    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        """加载插件清单"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            if manifest_path.suffix == '.yaml' or manifest_path.suffix == '.yml':
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        return PluginManifest(**data)

    def get_all_plugins(self) -> List[PluginInfo]:
        """获取所有插件信息"""
        return [plugin.get_info() for plugin in self.plugins.values()]

    def get_plugin(self, name: str) -> Optional[BinaryPlugin]:
        """获取指定插件"""
        return self.plugins.get(name)

    def start_plugin(self, name: str, config: Dict[str, Any] = None) -> bool:
        """启动插件"""
        plugin = self.get_plugin(name)
        if not plugin:
            logger.error(f"Plugin {name} not found")
            return False

        return plugin.start(config)

    def stop_plugin(self, name: str) -> bool:
        """停止插件"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False

        return plugin.stop()

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

    def cleanup(self):
        """清理所有插件"""
        self.process_pool.cleanup()
