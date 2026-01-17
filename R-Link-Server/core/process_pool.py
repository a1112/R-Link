"""
进程池管理器

管理插件的子进程
"""
import asyncio
import psutil
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
import json
import os

from .plugin_interface import PluginStatus, PluginState

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """进程信息"""
    plugin_name: str
    process: Optional[psutil.Popen] = None
    status: PluginStatus = PluginStatus.STOPPED
    start_time: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)
    port: Optional[int] = None
    log_file: Optional[str] = None


class ProcessPool:
    """进程池管理器"""

    def __init__(self):
        self.processes: Dict[str, ProcessInfo] = {}
        self.logs_dir = "logs"
        os.makedirs(self.logs_dir, exist_ok=True)

    def add_process(self, plugin_name: str, binary_path: str, config: Dict[str, Any] = None) -> bool:
        """添加进程到池"""
        if plugin_name in self.processes:
            logger.warning(f"Plugin {plugin_name} already exists in process pool")
            return False

        process_info = ProcessInfo(
            plugin_name=plugin_name,
            config=config or {},
            log_file=os.path.join(self.logs_dir, f"{plugin_name}.log")
        )
        self.processes[plugin_name] = process_info
        logger.info(f"Added plugin {plugin_name} to process pool")
        return True

    def remove_process(self, plugin_name: str) -> bool:
        """从池中移除进程"""
        if plugin_name not in self.processes:
            return False

        process_info = self.processes[plugin_name]
        if process_info.status == PluginStatus.RUNNING:
            self.stop_process(plugin_name)

        del self.processes[plugin_name]
        logger.info(f"Removed plugin {plugin_name} from process pool")
        return True

    def start_process(
        self,
        plugin_name: str,
        binary_path: str,
        args: list = None,
        env: Dict[str, str] = None,
        working_dir: str = None
    ) -> bool:
        """启动进程"""
        if plugin_name not in self.processes:
            self.add_process(plugin_name, binary_path)

        process_info = self.processes[plugin_name]

        if process_info.status == PluginStatus.RUNNING:
            logger.warning(f"Plugin {plugin_name} is already running")
            return False

        try:
            process_info.status = PluginStatus.STARTING

            # 准备命令
            cmd = [binary_path]
            if args:
                cmd.extend(args)

            # 准备环境变量
            process_env = os.environ.copy()
            if env:
                process_env.update(env)

            # 启动进程
            with open(process_info.log_file, 'a') as log_f:
                process = psutil.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=log_f,
                    env=process_env,
                    cwd=working_dir,
                    text=True
                )

            process_info.process = process
            process_info.start_time = datetime.now()

            # 检查进程是否成功启动
            if process.is_running():
                process_info.status = PluginStatus.RUNNING
                logger.info(f"Started plugin {plugin_name} (PID: {process.pid})")
                return True
            else:
                process_info.status = PluginStatus.ERROR
                logger.error(f"Failed to start plugin {plugin_name}")
                return False

        except Exception as e:
            process_info.status = PluginStatus.ERROR
            logger.error(f"Error starting plugin {plugin_name}: {e}")
            return False

    def stop_process(self, plugin_name: str, timeout: int = 10) -> bool:
        """停止进程"""
        if plugin_name not in self.processes:
            return False

        process_info = self.processes[plugin_name]

        if process_info.status != PluginStatus.RUNNING:
            return True

        process_info.status = PluginStatus.STOPPING

        try:
            process = process_info.process
            if process and process.is_running():
                # 尝试优雅关闭
                process.terminate()

                try:
                    process.wait(timeout=timeout)
                except psutil.TimeoutExpired:
                    # 强制终止
                    process.kill()
                    process.wait()

            process_info.status = PluginStatus.STOPPED
            process_info.process = None
            process_info.start_time = None
            logger.info(f"Stopped plugin {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Error stopping plugin {plugin_name}: {e}")
            process_info.status = PluginStatus.ERROR
            return False

    def restart_process(self, plugin_name: str) -> bool:
        """重启进程"""
        if plugin_name not in self.processes:
            return False

        process_info = self.processes[plugin_name]
        binary_path = process_info.process.exe() if process_info.process else None

        if not binary_path:
            logger.error(f"Cannot restart plugin {plugin_name}: no binary path")
            return False

        self.stop_process(plugin_name)
        return self.start_process(plugin_name, binary_path)

    def get_process_state(self, plugin_name: str) -> Optional[PluginState]:
        """获取进程状态"""
        if plugin_name not in self.processes:
            return None

        process_info = self.processes[plugin_name]

        # 更新状态
        if process_info.process:
            try:
                if process_info.process.is_running():
                    process_info.status = PluginStatus.RUNNING
                else:
                    process_info.status = PluginStatus.STOPPED
            except:
                process_info.status = PluginStatus.ERROR

        # 计算运行时间
        uptime = 0
        if process_info.start_time and process_info.status == PluginStatus.RUNNING:
            uptime = (datetime.now() - process_info.start_time).total_seconds()

        # 获取资源使用情况
        memory_usage = 0
        cpu_usage = 0
        try:
            if process_info.process and process_info.process.is_running():
                memory_usage = process_info.process.memory_info().rss / 1024 / 1024  # MB
                cpu_usage = process_info.process.cpu_percent(interval=0.1)
        except:
            pass

        return PluginState(
            status=process_info.status,
            pid=process_info.process.pid if process_info.process else None,
            port=process_info.port,
            uptime=uptime,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage
        )

    def get_all_states(self) -> Dict[str, PluginState]:
        """获取所有进程状态"""
        return {
            name: self.get_process_state(name)
            for name in self.processes.keys()
        }

    def get_process_logs(self, plugin_name: str, lines: int = 100) -> str:
        """获取进程日志"""
        if plugin_name not in self.processes:
            return ""

        process_info = self.processes[plugin_name]
        log_file = process_info.log_file

        if not log_file or not os.path.exists(log_file):
            return ""

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            logger.error(f"Error reading logs for {plugin_name}: {e}")
            return ""

    def cleanup(self):
        """清理所有进程"""
        for plugin_name in list(self.processes.keys()):
            self.stop_process(plugin_name)
