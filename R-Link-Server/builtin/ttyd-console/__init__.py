"""
TTYD 控制台插件 - 内置 Python 插件
使用 ttyd.exe 提供浏览器终端访问
"""
import os
import sys
import subprocess
import time
import signal
import logging
import json
import socket
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class TTYDManager:
    """TTYD 服务管理器"""

    def __init__(self, plugin_dir: str, config: Dict[str, Any] = None):
        self.plugin_dir = Path(plugin_dir)
        self.config = config or {}

        # 配置参数
        self.ttyd_path = self.config.get("ttyd_path", "ttyd.exe")
        self.ttyd_port = self.config.get("ttyd_port", 7681)
        self.command = self.config.get("command", "cmd.exe")
        self.enable_nginx_proxy = self.config.get("enable_nginx_proxy", True)
        self.nginx_location = self.config.get("nginx_location", "/console")

        # 完整路径
        self.ttyd_full_path = self.plugin_dir / self.ttyd_path
        self.config_file = self.plugin_dir / "config" / "settings.json"

        # 进程
        self.process: Optional[subprocess.Popen] = None
        self.pid_file = self.plugin_dir / "ttyd.pid"

    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return True
            except OSError:
                return False

    def _find_ttyd(self) -> Optional[Path]:
        """查找 ttyd.exe"""
        # 检查插件目录
        if self.ttyd_full_path.exists():
            return self.ttyd_full_path

        # 检查环境变量 PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            ttyd = Path(path) / "ttyd.exe"
            if ttyd.exists():
                return ttyd

        # 检查常见安装位置
        common_paths = [
            Path("C:/Program Files/ttyd/ttyd.exe"),
            Path("C:/ttyd/ttyd.exe"),
            Path("./ttyd.exe"),
        ]
        for path in common_paths:
            if path.exists():
                return path

        return None

    def _get_nginx_config_path(self) -> Optional[Path]:
        """获取 nginx 配置文件路径"""
        nginx_dir = self.plugin_dir.parent / "nginx-plugin"
        if nginx_dir.exists():
            config_dir = nginx_dir / "conf"
            if config_dir.exists():
                return config_dir / "nginx.conf"
        return None

    def _update_nginx_config(self) -> bool:
        """更新 nginx 配置以代理 ttyd"""
        if not self.enable_nginx_proxy:
            return True

        nginx_config = self._get_nginx_config_path()
        if not nginx_config:
            logger.warning("Nginx config not found, skipping nginx configuration")
            return False

        try:
            # 读取现有配置
            with open(nginx_config, 'r', encoding='utf-8') as f:
                config_content = f.read()

            # 检查是否已存在 ttyd 配置
            ttyd_location = f"location {self.nginx_location}"

            if ttyd_location in config_content:
                logger.info("Nginx already configured for ttyd")
                return True

            # 添加 ttyd 代理配置
            proxy_config = f"""

    {ttyd_location} {{
        proxy_pass http://127.0.0.1:{self.ttyd_port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }}
"""

            # 在 http 块的最后一个 server 块中添加
            # 简单处理：在文件末尾添加（需要手动调整）
            with open(nginx_config, 'a', encoding='utf-8') as f:
                f.write(proxy_config)

            logger.info(f"Added nginx proxy config for ttyd at {self.nginx_location}")
            return True

        except Exception as e:
            logger.error(f"Failed to update nginx config: {e}")
            return False

    def is_running(self) -> bool:
        """检查 ttyd 是否正在运行"""
        # 检查 PID 文件
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                # 检查进程是否存在
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    # 进程不存在，清理 PID 文件
                    self.pid_file.unlink()
            except (ValueError, OSError):
                pass

        # 检查端口是否被占用
        return not self._is_port_available(self.ttyd_port)

    def start(self) -> Dict[str, Any]:
        """启动 ttyd 服务"""
        if self.is_running():
            return {
                "success": True,
                "message": "ttyd is already running",
                "pid": self._read_pid(),
            }

        # 查找 ttyd.exe
        ttyd_exe = self._find_ttyd()
        if not ttyd_exe:
            return {
                "success": False,
                "error": f"ttyd.exe not found. Please install ttyd from https://github.com/tsl0922/ttyd"
            }

        # 检查端口
        if not self._is_port_available(self.ttyd_port):
            return {
                "success": False,
                "error": f"Port {self.ttyd_port} is already in use"
            }

        try:
            # 构建 ttyd 命令
            cmd = [
                str(ttyd.exe if hasattr(ttyd, 'exe') else ttyd_exe),
                "-p", str(self.ttyd_port),
                "-b", "/",
            ]

            # 添加命令
            cmd.append(self.command)

            logger.info(f"Starting ttyd: {' '.join(cmd)}")

            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.ttyd_exe.parent) if hasattr(ttyd_exe, 'parent') else str(ttyd_exe.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # 保存 PID
            self._write_pid(self.process.pid)

            # 等待启动
            time.sleep(2)

            # 检查是否成功启动
            if self.process.poll() is None:
                logger.info(f"ttyd started successfully on port {self.ttyd_port}")

                # 更新 nginx 配置
                self._update_nginx_config()

                return {
                    "success": True,
                    "message": "ttyd started successfully",
                    "pid": self.process.pid,
                    "port": self.ttyd_port,
                    "url": self.get_url(),
                }
            else:
                # 启动失败
                stderr = self.process.stderr.read().decode('utf-8', errors='ignore')
                return {
                    "success": False,
                    "error": f"ttyd failed to start: {stderr}"
                }

        except Exception as e:
            logger.error(f"Error starting ttyd: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def stop(self) -> Dict[str, Any]:
        """停止 ttyd 服务"""
        if not self.is_running():
            return {
                "success": True,
                "message": "ttyd is not running"
            }

        try:
            # 读取 PID
            if self.pid_file.exists():
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())

                # 终止进程
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                 capture_output=True)
                else:
                    os.kill(pid, signal.SIGTERM)

                # 清理 PID 文件
                self.pid_file.unlink()

            # 如果有进程对象，也尝试终止
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()

            self.process = None

            logger.info("ttyd stopped")
            return {
                "success": True,
                "message": "ttyd stopped successfully"
            }

        except Exception as e:
            logger.error(f"Error stopping ttyd: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def restart(self) -> Dict[str, Any]:
        """重启 ttyd 服务"""
        self.stop()
        time.sleep(1)
        return self.start()

    def get_status(self) -> Dict[str, Any]:
        """获取 ttyd 状态"""
        running = self.is_running()

        return {
            "running": running,
            "pid": self._read_pid() if running else None,
            "port": self.ttyd_port,
            "command": self.command,
            "url": self.get_url() if running else None,
            "ttyd_found": self._find_ttyd() is not None,
        }

    def get_url(self) -> str:
        """获取控制台访问地址"""
        if self.enable_nginx_proxy:
            # 通过 nginx 代理访问
            return self.nginx_location
        else:
            # 直接访问
            return f"http://127.0.0.1:{self.ttyd_port}"

    def _read_pid(self) -> Optional[int]:
        """读取 PID"""
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    return int(f.read().strip())
            except (ValueError, OSError):
                pass
        return None

    def _write_pid(self, pid: int):
        """写入 PID"""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, 'w') as f:
            f.write(str(pid))


class Plugin:
    """TTYD 控制台插件主类"""

    def __init__(self, config: Dict[str, Any] = None, plugin_dir: str = None):
        self.config = config or {}
        self.plugin_dir = plugin_dir or Path(__file__).parent
        self.status = "running"
        self.ttyd = TTYDManager(self.plugin_dir, self.config)

    def get_info(self):
        """获取插件信息"""
        return {
            "name": "ttyd-console",
            "version": "1.0.0",
            "description": "Web 控制台插件 - 使用 ttyd.exe 提供浏览器终端访问",
            "author": "R-Link Team",
            "binary_path": __file__,
        }

    def start(self, config: Dict[str, Any] = None) -> bool:
        """启动插件"""
        self.status = "running"
        return True

    def stop(self) -> bool:
        """停止插件"""
        # 停止 ttyd 服务
        self.ttyd.stop()
        self.status = "stopped"
        return True

    def restart(self) -> bool:
        """重启插件"""
        return self.ttyd.restart().get("success", False)

    def get_status(self):
        """获取插件状态"""
        ttyd_status = self.ttyd.get_status()

        return {
            "status": "running" if ttyd_status["running"] else "stopped",
            "pid": ttyd_status.get("pid"),
            "port": ttyd_status.get("port"),
            "uptime": 0,
            "ttyd_running": ttyd_status["running"],
            "console_url": ttyd_status.get("url"),
        }

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "ttyd_path": self.config.get("ttyd_path", "ttyd.exe"),
            "ttyd_port": self.config.get("ttyd_port", 7681),
            "command": self.config.get("command", "cmd.exe"),
            "enable_nginx_proxy": self.config.get("enable_nginx_proxy", True),
            "nginx_location": self.config.get("nginx_location", "/console"),
        }

    def set_config(self, config: Dict[str, Any]) -> bool:
        """设置配置"""
        self.config.update(config)
        # 更新 ttyd 管理器配置
        self.ttyd = TTYDManager(self.plugin_dir, self.config)
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return self.ttyd._find_ttyd() is not None

    def get_logs(self, lines: int = 100) -> str:
        """获取日志"""
        return "TTYD Console plugin - Manage ttyd.exe for web terminal access"

    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Any:
        """执行命令"""
        if command == "start_ttyd":
            return self.ttyd.start()

        elif command == "stop_ttyd":
            return self.ttyd.stop()

        elif command == "restart_ttyd":
            return self.ttyd.restart()

        elif command == "get_status":
            return self.ttyd.get_status()

        elif command == "get_url":
            return {"url": self.ttyd.get_url()}

        else:
            return {"error": f"Unknown command: {command}"}


# 插件入口点
plugin = Plugin
