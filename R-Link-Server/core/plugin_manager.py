"""
Plugin Manager

Responsible for plugin discovery, loading, and management
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
    """Plugin Manifest"""
    name: str
    version: str
    description: str
    author: str
    binary: str
    config_template: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    commands: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    icon: Optional[str] = None
    category: str = "general"
    builtin: bool = False
    ui_template: Optional[str] = None  # Frontend template name


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
    """Plugin Manager"""

    def __init__(self, plugins_dir: str = "plugins", builtin_dir: str = "builtin"):
        self.plugins_dir = plugins_dir
        self.builtin_dir = builtin_dir
        self.plugins: Dict[str, BinaryPlugin] = {}
        self.process_pool = ProcessPool()
        self._load_plugins()

    def _load_plugins(self):
        """Load all plugins (user + builtin)"""
        # Load user plugins
        self._load_from_dir(self.plugins_dir, "user")

        # Load builtin plugins
        self._load_from_dir(self.builtin_dir, "builtin")

    def _load_from_dir(self, dir_path: str, dir_type: str):
        """Load plugins from specified directory"""
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

            manifest_file = plugin_dir / "manifest.yaml"
            if not manifest_file.exists():
                manifest_file = plugin_dir / "manifest.json"

            if not manifest_file.exists():
                logger.warning(f"No manifest found in {plugin_dir.name}")
                continue

            try:
                manifest = self._load_manifest(manifest_file)

                # If no builtin field, set based on directory type
                if not hasattr(manifest, 'builtin'):
                    manifest.builtin = (dir_type == "builtin")

                plugin = BinaryPlugin(
                    manifest=manifest,
                    plugin_dir=str(plugin_dir),
                    process_pool=self.process_pool
                )
                self.plugins[manifest.name] = plugin
                logger.info(f"Loaded {dir_type} plugin: {manifest.name} v{manifest.version}")

            except Exception as e:
                logger.error(f"Error loading {dir_type} plugin {plugin_dir.name}: {e}")

    def _load_manifest(self, manifest_path: Path) -> PluginManifest:
        """Load plugin manifest"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            if manifest_path.suffix == '.yaml' or manifest_path.suffix == '.yml':
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        return PluginManifest(**data)

    def get_all_plugins(self) -> List[PluginInfo]:
        """Get all plugin info"""
        return [plugin.get_info() for plugin in self.plugins.values()]

    def get_plugin(self, name: str) -> Optional[BinaryPlugin]:
        """Get specified plugin"""
        return self.plugins.get(name)

    def is_builtin(self, name: str) -> bool:
        """Check if plugin is builtin"""
        plugin = self.get_plugin(name)
        return plugin is not None and plugin.manifest.builtin if plugin else False

    def get_builtin_plugins(self) -> List[str]:
        """Get all builtin plugin names"""
        return [name for name, plugin in self.plugins.items() if plugin.manifest.builtin]

    def get_user_plugins(self) -> List[str]:
        """Get all user plugin names"""
        return [name for name, plugin in self.plugins.items() if not plugin.manifest.builtin]

    def start_plugin(self, name: str, config: Dict[str, Any] = None) -> bool:
        """Start plugin"""
        plugin = self.get_plugin(name)
        if not plugin:
            logger.error(f"Plugin {name} not found")
            return False
        return plugin.start(config)

    def stop_plugin(self, name: str) -> bool:
        """Stop plugin (builtin plugins cannot be stopped)"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False
        if plugin.manifest.builtin:
            logger.warning(f"Cannot stop builtin plugin: {name}")
            return False
        return plugin.stop()

    def restart_plugin(self, name: str) -> bool:
        """Restart plugin"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False
        return plugin.restart()

    def get_plugin_status(self, name: str) -> Optional[PluginState]:
        """Get plugin status"""
        plugin = self.get_plugin(name)
        if not plugin:
            return None
        return plugin.get_status()

    def get_all_statuses(self) -> Dict[str, PluginState]:
        """Get all plugin statuses"""
        return {
            name: plugin.get_status()
            for name, plugin in self.plugins.items()
        }

    def get_plugin_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get plugin config"""
        plugin = self.get_plugin(name)
        if not plugin:
            return None
        return plugin.get_config()

    def set_plugin_config(self, name: str, config: Dict[str, Any]) -> bool:
        """Set plugin config"""
        plugin = self.get_plugin(name)
        if not plugin:
            return False
        return plugin.set_config(config)

    def get_plugin_logs(self, name: str, lines: int = 100) -> str:
        """Get plugin logs"""
        plugin = self.get_plugin(name)
        if not plugin:
            return ""
        return plugin.get_logs(lines)

    def cleanup(self):
        """Cleanup all plugins"""
        self.process_pool.cleanup()
