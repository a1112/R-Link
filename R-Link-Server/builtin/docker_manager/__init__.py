"""
Docker 管理插件 - 内置 Python 插件
支持 Docker 容器的管理、镜像管理、网络管理等
"""
import os
import subprocess
import threading
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class DockerManager:
    """Docker 管理器"""

    def __init__(self):
        self.docker_path = self._find_docker()
        self.available = self.docker_path is not None

    def _find_docker(self) -> Optional[str]:
        """查找 Docker 可执行文件"""
        if platform.system() == "Windows":
            paths = [
                r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
                r"C:\Program Files\Docker\Docker\resources\com.docker.cli.winamd64\docker.exe",
            ]
            for path in paths:
                if os.path.exists(path):
                    return path
        else:
            return "docker"

        return None

    def _run_command(self, args: List[str]) -> Dict[str, Any]:
        """执行 Docker 命令"""
        if not self.available:
            return {"error": "Docker is not available"}

        try:
            cmd = [self.docker_path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.stderr and "command not found" in result.stderr.lower():
                return {"error": "Docker command not found", "available": False}

            try:
                output = json.loads(result.stdout) if result.stdout else {}
                return {"success": result.returncode == 0, "data": output}
            except json.JSONDecodeError:
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "code": result.returncode
                }

        except subprocess.TimeoutExpired:
            return {"error": "Command timeout"}
        except FileNotFoundError:
            self.available = False
            return {"error": "Docker not found", "available": False}
        except Exception as e:
            return {"error": str(e)}

    def check_available(self) -> Dict[str, Any]:
        """检查 Docker 是否可用"""
        return {
            "available": self.available,
            "path": self.docker_path,
        }

    def version(self) -> Dict[str, Any]:
        """获取 Docker 版本"""
        if not self.available:
            return {"error": "Docker not available"}

        result = self._run_command(["--version"])
        if result.get("error"):
            return result

        # 解析版本信息
        version_info = result.get("stdout", "")
        return {
            "version": version_info.strip(),
            "available": True
        }

    def info(self) -> Dict[str, Any]:
        """获取 Docker 系统信息"""
        result = self._run_command(["info", "--format", "{{json .}}"])
        if result.get("error"):
            return result

        return {
            "info": result.get("data", {}),
            "available": self.available
        }

    def list_containers(self, all: bool = False) -> Dict[str, Any]:
        """列出容器"""
        args = ["ps", "-a"]
        if all:
            args.append("-a")
        args.extend(["--format", "{{json .}}"])

        result = self._run_command(args)
        if result.get("error"):
            return result

        try:
            containers = json.loads(result["stdout"])
            return {
                "containers": containers,
                "count": len(containers)
            }
        except:
            return {"error": "Failed to parse output", "raw": result["stdout"]}

    def list_images(self) -> Dict[str, Any]:
        """列出镜像"""
        result = self._run_command(["images", "--format", "{{json .}}"])
        if result.get("error"):
            return result

        try:
            images = json.loads(result["stdout"])
            return {
                "images": images,
                "count": len(images)
            }
        except:
            return {"error": "Failed to parse output", "raw": result["stdout"]}

    def get_container(self, container_id: str) -> Dict[str, Any]:
        """获取容器详情"""
        result = self._run_command(["inspect", container_id, "--format", "{{json .}}"])
        if result.get("error"):
            return result

        try:
            return {"container": json.loads(result["stdout"])}
        except:
            return {"error": "Failed to parse output"}

    def get_container_logs(self, container_id: str, tail: int = 100) -> Dict[str, Any]:
        """获取容器日志"""
        args = ["logs", container_id]
        if tail:
            args.extend(["--tail", str(tail)])

        result = self._run_command(args)
        if result.get("error"):
            return result

        return {
            "container_id": container_id,
            "logs": result.get("stdout", "")
        }

    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """获取容器统计信息"""
        result = self._run_command(["stats", container_id, "--no-stream", "--format", "{{json .}}"])
        if result.get("error"):
            return result

        try:
            return {"stats": json.loads(result["stdout"])}
        except:
            return {"error": "Failed to parse stats"}

    def start_container(self, container_id: str) -> Dict[str, Any]:
        """启动容器"""
        result = self._run_command(["start", container_id])
        if result.get("error"):
            return result

        return {"success": result["code"] == 0, "message": "Container started"}

    def stop_container(self, container_id: str) -> Dict[str, Any]:
        """停止容器"""
        result = self._run_command(["stop", container_id])
        if result.get("error"):
            return result

        return {"success": result["code"] == 0, "message": "Container stopped"}

    def restart_container(self, container_id: str) -> Dict[str, Any]:
        """重启容器"""
        result = self._run_command(["restart", container_id])
        if result.get("error"):
            return result

        return {"success": result["code"] == 0, "message": "Container restarted"}

    def remove_container(self, container_id: str, force: bool = False) -> Dict[str, Any]:
        """删除容器"""
        args = ["rm", container_id]
        if force:
            args.append("-f")

        result = self._run_command(args)
        if result.get("error"):
            return result

        return {"success": result["code"] == 0, "message": "Container removed"}

    def create_container(
        self,
        image: str,
        name: str = None,
        ports: Dict[str, str] = None,
        volumes: Dict[str, str] = None,
        env: Dict[str, str] = None,
        command: List[str] = None,
        auto_remove: bool = False,
    ) -> Dict[str, Any]:
        """创建并启动容器"""
        args = ["run", "-d"]

        if name:
            args.extend(["--name", name])

        if auto_remove:
            args.append("--rm")

        if ports:
            for container_port, host_port in ports.items():
                args.extend(["-p", f"{host_port}:{container_port}"])

        if volumes:
            for host_path, container_path in volumes.items():
                args.extend(["-v", f"{host_path}:{container_path}"])

        if env:
            for key, value in env.items():
                args.extend(["-e", f"{key}={value}"])

        args.append(image)

        if command:
            args.extend(command)

        result = self._run_command(args)
        if result.get("error"):
            return result

        try:
            # 获取容器ID
            container_id = result["stdout"].strip()
            return {
                "success": True,
                "container_id": container_id,
                "message": "Container created and started"
            }
        except:
            return {"error": "Failed to parse container ID"}

    def pull_image(self, image: str) -> Dict[str, Any]:
        """拉取镜像"""
        # 在后台线程中拉取
        def pull():
            return self._run_command(["pull", image])

        thread = threading.Thread(target=pull, daemon=True)
        thread.start()

        return {
            "success": True,
            "message": f"Pulling image {image}",
            "image": image
        }

    def remove_image(self, image: str, force: bool = False) -> Dict[str, Any]:
        """删除镜像"""
        args = ["rmi", image]
        if force:
            args.append("-f")

        result = self._run_command(args)
        if result.get("error"):
            return result

        return {"success": result["code"] == 0, "message": "Image removed"}

    def list_networks(self) -> Dict[str, Any]:
        """列出网络"""
        result = self._run_command(["network", "ls", "--format", "{{json .}}"])
        if result.get("error"):
            return result

        try:
            networks = json.loads(result["stdout"])
            return {"networks": networks, "count": len(networks)}
        except:
            return {"error": "Failed to parse output"}

    def list_volumes(self) -> Dict[str, Any]:
        """列出卷"""
        result = self._run_command(["volume", "ls", "--format", "{{json .}}"])
        if result.get("error"):
            return result

        try:
            volumes = json.loads(result["stdout"])
            return {"volumes": volumes, "count": len(volumes)}
        except:
            return {"error": "Failed to parse output"}

    def get_system_stats(self) -> Dict[str, Any]:
        """获取 Docker 系统统计"""
        # 获取容器统计
        containers_result = self.list_containers(all=True)
        if containers_result.get("error"):
            return containers_result

        # 获取镜像统计
        images_result = self.list_images()
        if images_result.get("error"):
            return images_result

        return {
            "containers": {
                "total": len(containers_result.get("containers", [])),
                "running": len([c for c in containers_result.get("containers", []) if c.get("State") == "running"]),
            },
            "images": {
                "total": images_result.get("count", 0),
            },
            "available": self.available
        }


class Plugin:
    """Docker 管理插件主类"""

    def __init__(self, config: Dict[str, Any] = None, plugin_dir: str = None):
        self.config = config or {}
        self.plugin_dir = plugin_dir or Path(__file__).parent
        self.docker = DockerManager()
        self.status = "running"

    def get_info(self):
        """获取插件信息"""
        return {
            "name": "docker-manager",
            "version": "1.0.0",
            "description": "Docker 容器管理插件 - 支持容器、镜像、网络和卷的管理",
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
            "docker_available": self.docker.available,
        }

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "auto_refresh": self.config.get("auto_refresh", True),
            "refresh_interval": self.config.get("refresh_interval", 5),
        }

    def set_config(self, config: Dict[str, Any]) -> bool:
        """设置配置"""
        self.config.update(config)
        return True

    def health_check(self) -> bool:
        """健康检查"""
        return self.docker.available

    def get_logs(self, lines: int = 100) -> str:
        """获取日志"""
        return "Docker Manager plugin - Use specific container commands for logs"

    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Any:
        """执行命令"""
        if command == "check_available":
            return self.docker.check_available()

        elif command == "version":
            return self.docker.version()

        elif command == "info":
            return self.docker.info()

        elif command == "list_containers":
            return self.docker.list_containers(all=args.get("all", False) if args else False)

        elif command == "list_images":
            return self.docker.list_images()

        elif command == "get_container":
            container_id = args.get("container_id") if args else None
            if not container_id:
                return {"error": "container_id required"}
            return self.docker.get_container(container_id)

        elif command == "get_container_logs":
            container_id = args.get("container_id") if args else None
            tail = args.get("tail", 100) if args else 100
            if not container_id:
                return {"error": "container_id required"}
            return self.docker.get_container_logs(container_id, tail)

        elif command == "get_container_stats":
            container_id = args.get("container_id") if args else None
            if not container_id:
                return {"error": "container_id required"}
            return self.docker.get_container_stats(container_id)

        elif command == "start_container":
            container_id = args.get("container_id") if args else None
            if not container_id:
                return {"error": "container_id required"}
            return self.docker.start_container(container_id)

        elif command == "stop_container":
            container_id = args.get("container_id") if args else None
            if not container_id:
                return {"error": "container_id required"}
            return self.docker.stop_container(container_id)

        elif command == "restart_container":
            container_id = args.get("container_id") if args else None
            if not container_id:
                return {"error": "container_id required"}
            return self.docker.restart_container(container_id)

        elif command == "remove_container":
            container_id = args.get("container_id") if args else None
            if not container_id:
                return {"error": "container_id required"}
            return self.docker.remove_container(container_id, force=args.get("force", False) if args else False)

        elif command == "create_container":
            image = args.get("image") if args else None
            if not image:
                return {"error": "image required"}

            return self.docker.create_container(
                image=image,
                name=args.get("name"),
                ports=args.get("ports"),
                volumes=args.get("volumes"),
                env=args.get("env"),
                command=args.get("command"),
                auto_remove=args.get("auto_remove", False),
            )

        elif command == "pull_image":
            image = args.get("image") if args else None
            if not image:
                return {"error": "image required"}
            return self.docker.pull_image(image)

        elif command == "remove_image":
            image = args.get("image") if args else None
            if not image:
                return {"error": "image required"}
            return self.docker.remove_image(image, force=args.get("force", False) if args else False)

        elif command == "list_networks":
            return self.docker.list_networks()

        elif command == "list_volumes":
            return self.docker.list_volumes()

        elif command == "get_system_stats":
            return self.docker.get_system_stats()

        else:
            return {"error": f"Unknown command: {command}"}


# 插件入口点
plugin = Plugin
