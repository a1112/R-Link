"""
系统相关的 API 路由
"""
from fastapi import APIRouter
import psutil
import platform
from datetime import datetime
from typing import Dict, Any
import os

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
async def get_system_info():
    """获取系统信息"""
    return {
        "hostname": platform.node(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version()
    }


@router.get("/resources")
async def get_system_resources():
    """获取系统资源使用情况"""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()

    # 内存
    memory = psutil.virtual_memory()

    # 磁盘
    disk = psutil.disk_usage('/')

    return {
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count
        },
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }
    }


@router.get("/processes")
async def list_processes():
    """获取系统进程列表"""
    processes = []

    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']):
        try:
            processes.append({
                "pid": proc.info['pid'],
                "name": proc.info['name'],
                "username": proc.info.get('username'),
                "cpu_percent": proc.info.get('cpu_percent', 0),
                "memory_mb": proc.info['memory_info'].rss / 1024 / 1024 if proc.info.get('memory_info') else 0
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return processes


@router.get("/uptime")
async def get_system_uptime():
    """获取系统运行时间"""
    boot_time = psutil.boot_time()
    uptime = datetime.now().timestamp() - boot_time

    return {
        "boot_time": boot_time,
        "uptime_seconds": uptime,
        "uptime_human": _format_uptime(uptime)
    }


def _format_uptime(seconds: float) -> str:
    """格式化运行时间"""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
