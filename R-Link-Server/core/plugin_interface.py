"""
插件接口定义

所有插件必须实现此接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum


class PluginStatus(Enum):
    """插件状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class PluginInfo:
    """插件基本信息"""
    name: str                    # 插件名称
    version: str                 # 版本号
    description: str             # 描述
    author: str                  # 作者
    binary_path: str             # 二进制文件路径
    config_path: Optional[str]   # 配置文件路径
    icon: Optional[str] = None   # 图标路径


@dataclass
class PluginState:
    """插件运行状态"""
    status: PluginStatus
    pid: Optional[int] = None
    port: Optional[int] = None
    uptime: float = 0            # 运行时间（秒）
    memory_usage: float = 0      # 内存使用（MB）
    cpu_usage: float = 0         # CPU使用率（%）
    last_error: Optional[str] = None


class IPlugin(ABC):
    """插件接口，所有插件必须实现此接口"""

    @abstractmethod
    def get_info(self) -> PluginInfo:
        """获取插件信息"""
        pass

    @abstractmethod
    def start(self, config: Dict[str, Any] = None) -> bool:
        """启动插件"""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """停止插件"""
        pass

    @abstractmethod
    def restart(self) -> bool:
        """重启插件"""
        pass

    @abstractmethod
    def get_status(self) -> PluginState:
        """获取插件状态"""
        pass

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """获取插件配置"""
        pass

    @abstractmethod
    def set_config(self, config: Dict[str, Any]) -> bool:
        """设置插件配置"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass

    @abstractmethod
    def get_logs(self, lines: int = 100) -> str:
        """获取日志"""
        pass

    @abstractmethod
    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Any:
        """执行自定义命令"""
        pass
