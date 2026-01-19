"""
软件自动安装插件 - 内置插件
支持检测和安装系统软件（Docker、Git、Node.js 等）
"""
import os
import platform
import subprocess
import logging
import threading
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

logger = logging.getLogger(__name__)


class SoftwareInstaller:
    """软件安装器"""

    # 软件下载 URLs 和检测方法
    SOFTWARES = {
        "docker": {
            "display_name": "Docker",
            "windows": {
                "download_url": "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
                "install_cmd": None,  # 使用下载的安装程序
                "check_cmd": ["docker", "--version"],
                "size_mb": 500,
            },
            "linux": {
                "check_cmd": ["docker", "--version"],
                "install_cmd": ["curl", "-fsSL", "https://get.docker.com", "-o", "get-docker.sh", "sh", "get-docker.sh"],
                "install_cmd_dnf": ["sudo", "dnf", "install", "-y", "docker"],
                "install_cmd_apt": ["sudo", "apt-get", "update", "&&", "sudo", "apt-get", "install", "-y", "docker.io"],
            },
            "darwin": {
                "check_cmd": ["docker", "--version"],
                "install_cmd": ["brew", "install", "--cask", "docker"],
            }
        },
        "docker-compose": {
            "display_name": "Docker Compose",
            "windows": {
                "check_cmd": ["docker-compose", "--version"],
                "install_cmd": None,  # 随 Docker Desktop 一起安装
                "size_mb": 10,
            },
            "linux": {
                "check_cmd": ["docker-compose", "--version"],
                "install_cmd": ["sudo", "curl", "-L", "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)", "-o", "/usr/local/bin/docker-compose", "sudo", "chmod", "+x", "/usr/local/bin/docker-compose"],
            },
            "darwin": {
                "check_cmd": ["docker-compose", "--version"],
                "install_cmd": ["brew", "install", "docker-compose"],
            }
        },
        "git": {
            "display_name": "Git",
            "windows": {
                "check_cmd": ["git", "--version"],
                "install_cmd": ["winget", "install", "--id", "Git.Git"],
                "size_mb": 70,
            },
            "linux": {
                "check_cmd": ["git", "--version"],
                "install_cmd_dnf": ["sudo", "dnf", "install", "-y", "git"],
                "install_cmd_apt": ["sudo", "apt-get", "install", "-y", "git"],
            },
            "darwin": {
                "check_cmd": ["git", "--version"],
                "install_cmd": ["brew", "install", "git"],
            }
        },
        "nodejs": {
            "display_name": "Node.js",
            "windows": {
                "check_cmd": ["node", "--version"],
                "install_cmd": ["winget", "install", "-e", "--id", "OpenJS.NodeJS"],
                "size_mb": 35,
            },
            "linux": {
                "check_cmd": ["node", "--version"],
                "install_cmd_dnf": ["sudo", "dnf", "install", "-y", "nodejs", "npm"],
                "install_cmd_apt": ["sudo", "apt-get", "install", "-y", "nodejs", "npm"],
            },
            "darwin": {
                "check_cmd": ["node", "--version"],
                "install_cmd": ["brew", "install", "node"],
            }
        },
        "python3": {
            "display_name": "Python 3",
            "windows": {
                "check_cmd": ["python", "--version"],
                "install_cmd": ["winget", "install", "-e", "--id", "Python.Python.3.12"],
                "size_mb": 25,
            },
            "linux": {
                "check_cmd": ["python3", "--version"],
                "install_cmd_dnf": ["sudo", "dnf", "install", "-y", "python3", "python3-pip"],
                "install_cmd_apt": ["sudo", "apt-get", "install", "-y", "python3", "python3-pip"],
            },
            "darwin": {
                "check_cmd": ["python3", "--version"],
                "install_cmd": ["brew", "install", "python@3"],
            }
        },
    }

    def __init__(self):
        self.system = platform.system()
        self.machine = platform.machine()
        self.install_progress = {}

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "system": self.system,
            "machine": self.machine,
            "version": platform.version(),
            "node": platform.node(),
            "python_version": platform.python_version(),
        }

    def check_software(self, software: str) -> Dict[str, Any]:
        """检查软件是否安装"""
        if software not in self.SOFTWARES:
            return {"installed": False, "error": "Unknown software"}

        config = self.SOFTWARES[software]
        os_config = config.get(self.system.lower())

        if not os_config:
            return {"installed": False, "error": f"Not supported on {self.system}"}

        try:
            result = subprocess.run(
                os_config["check_cmd"],
                capture_output=True,
                text=True,
                timeout=5
            )
            installed = result.returncode == 0

            version = None
            if installed:
                # 解析版本信息
                output = result.stdout.strip()
                if software == "docker":
                    parts = output.split()
                    if len(parts) >= 3:
                        version = parts[2].strip(',')
                elif software == "git":
                    parts = output.split()
                    if len(parts) >= 3:
                        version = parts[2]
                elif "node" in software or "python" in software:
                    parts = output.split()
                    if len(parts) >= 2:
                        version = parts[1].strip('v')

            return {
                "installed": installed,
                "version": version,
                "display_name": config["display_name"]
            }
        except Exception as e:
            return {"installed": False, "error": str(e)}

    def check_all(self) -> Dict[str, Dict[str, Any]]:
        """检查所有支持的软件"""
        result = {}
        for software in self.SOFTWARES:
            result[software] = self.check_software(software)
        return result

    def install_software(self, software: str) -> Dict[str, Any]:
        """安装软件"""
        if software not in self.SOFTWARES:
            return {"success": False, "error": "Unknown software"}

        config = self.SOFTWARES[software]
        os_config = config.get(self.system.lower())

        if not os_config:
            return {"success": False, "error": f"Not supported on {self.system}"}

        try:
            if self.system == "Windows":
                return self._install_windows(software, config, os_config)
            elif self.system == "Linux":
                return self._install_linux(software, config, os_config)
            elif self.system == "Darwin":
                return self._install_macos(software, config, os_config)
            else:
                return {"success": False, "error": f"Unsupported system: {self.system}"}

        except Exception as e:
            logger.error(f"Error installing {software}: {e}")
            return {"success": False, "error": str(e)}

    def _install_windows(self, software: str, config: Dict, os_config: Dict) -> Dict[str, Any]:
        """Windows 安装"""
        install_cmd = os_config.get("install_cmd")
        size_mb = os_config.get("size_mb", 0)

        if not install_cmd:
            # 没有安装命令
            return {"success": False, "error": "Manual installation required"}

        try:
            if install_cmd[0] == "winget":
                # 使用 winget 安装
                result = subprocess.run(
                    install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode == 0:
                    return {
                        "success": True,
                        "message": f"{config['display_name']} installed successfully",
                        "restart_required": True
                    }
                else:
                    return {
                        "success": False,
                        "error": result.stderr or "Installation failed"
                    }
            else:
                # 直接运行安装程序
                return {"success": False, "error": "Manual installation required"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Installation timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _install_linux(self, software: str, config: Dict, os_config: Dict) -> Dict[str, Any]:
        """Linux 安装"""
        # 检查是否有权限
        if os.geteuid() != 0:
            return {"success": False, "error": "Root privileges required"}

        # 尝试不同的包管理器
        install_commands = []
        if "install_cmd" in os_config:
            install_commands.append(os_config["install_cmd"])
        if "install_cmd_dnf" in os_config:
            install_commands.append(os_config["install_cmd_dnf"])
        if "install_cmd_apt" in os_config:
            install_commands.append(os_config["install_cmd_apt"])

        for cmd in install_commands:
            try:
                # 分割命令字符串
                if isinstance(cmd, str):
                    # 简单的字符串命令，需要解析
                    if "&&" in cmd:
                        # 复合命令
                        parts = cmd.split("&&")
                        for part in parts:
                            subprocess.run(part.strip().split(), check=True)
                    else:
                        subprocess.run(cmd.split(), check=True)
                else:
                    subprocess.run(cmd, check=True)

                return {
                    "success": True,
                    "message": f"{config['display_name']} installed successfully"
                }

            except FileNotFoundError:
                continue
            except subprocess.CalledProcessError:
                continue

        return {"success": False, "error": "No suitable package manager found"}

    def _install_macos(self, software: str, config: Dict, os_config: Dict) -> Dict[str, Any]:
        """macOS 安装"""
        install_cmd = os_config.get("install_cmd")

        if not install_cmd:
            return {"success": False, "error": "Manual installation required"}

        try:
            # 检查是否安装了 Homebrew
            brew_check = subprocess.run(
                ["which", "brew"],
                capture_output=True
            )

            if brew_check.returncode != 0:
                return {
                    "success": False,
                    "error": "Homebrew not installed. Please install from https://brew.sh"
                }

            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"{config['display_name']} installed successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "Installation failed"
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Installation timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class Plugin:
    """插件主类"""

    def __init__(self, config: Dict[str, Any] = None, plugin_dir: str = None):
        self.config = config or {}
        self.plugin_dir = plugin_dir or Path(__file__).parent
        self.installer = SoftwareInstaller()
        self.status = "running"

    def get_info(self):
        """获取插件信息"""
        return {
            "name": "software-installer",
            "version": "1.0.0",
            "description": "软件自动安装插件 - 支持 Docker、Git、Node.js 等软件的检测和安装",
            "author": "R-Link",
            "binary_path": __file__,
        }

    def start(self, config: Dict[str, Any] = None) -> bool:
        """启动插件"""
        self.status = "running"
        return True

    def stop(self) -> bool:
        """停止插件"""
        self.status = "stopped"
        return True

    def restart(self) -> bool:
        """重启插件"""
        return True

    def get_status(self):
        """获取插件状态"""
        return {
            "status": self.status,
            "pid": None,
            "port": None,
            "uptime": 0,
        }

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "auto_check": self.config.get("auto_check", True),
            "check_interval": self.config.get("check_interval", 3600),
            "notify_updates": self.config.get("notify_updates", True),
        }

    def set_config(self, config: Dict[str, Any]) -> bool:
        """设置配置"""
        self.config.update(config)
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return self.status == "running"

    def get_logs(self, lines: int = 100) -> str:
        """获取日志"""
        return "Software installer plugin - No logs available"

    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Any:
        """执行命令"""
        if command == "get_system_info":
            return self.installer.get_system_info()

        elif command == "check_all":
            return self.installer.check_all()

        elif command == "check_software":
            software = args.get("software") if args else None
            if not software:
                return {"error": "Software name required"}
            return self.installer.check_software(software)

        elif command == "install_software":
            software = args.get("software") if args else None
            if not software:
                return {"error": "Software name required"}

            # 异步安装（在后台线程中执行）
            def install_in_background():
                return self.installer.install_software(software)

            thread = threading.Thread(target=install_in_background, daemon=True)
            thread.start()

            return {
                "success": True,
                "message": f"Installation of {software} started in background"
            }

        elif command == "get_available_software":
            return {
                "software": list(self.installer.SOFTWARES.keys()),
                "details": {
                    name: {
                        "display_name": info["display_name"],
                        "description": f"{info['display_name']} for {self.installer.system}"
                    }
                    for name, info in self.installer.SOFTWARES.items()
                }
            }

        else:
            return {"error": f"Unknown command: {command}"}


# 插件入口点
plugin = Plugin
