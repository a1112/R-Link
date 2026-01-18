#!/usr/bin/env python3
"""
R-Link Nginx 插件
管理 Nginx 反向代理服务
"""

import argparse
import json
import os
import sys
import time
import signal
import subprocess
from datetime import datetime

running = True
config = {
    "nginx_path": "nginx.exe",
    "config_dir": "conf",
    "port": 80,
    "worker_processes": 4,
    "max_connections": 1024,
    "keepalive_timeout": 65
}

def signal_handler(signum, frame):
    global running
    print(f"[{datetime.now()}] [NGINX-PLUGIN] Received signal {signum}, shutting down...")
    running = False

def load_config(config_path):
    """加载配置文件"""
    global config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            config.update(loaded)
    except Exception as e:
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Using default config")

def save_config(config_path):
    """保存配置文件"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Config saved")
    except Exception as e:
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Failed to save config: {e}")

def get_nginx_status():
    """检查 Nginx 是否正在运行"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME", "eq", "nginx.exe"],
            capture_output=True,
            text=True
        )
        return "nginx.exe" in result.stdout
    except:
        return False

def start_nginx():
    """启动 Nginx"""
    nginx_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), config["nginx_path"])

    if not os.path.exists(nginx_exe):
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx not found at: {nginx_exe}")
        return False

    if get_nginx_status():
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx is already running")
        return True

    try:
        # 检查配置文件
        config_dir = config.get("config_dir", "conf")
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_dir, "nginx.conf")

        if not os.path.exists(config_file):
            # 创建基本配置文件
            print(f"[{datetime.now()}] [NGINX-PLUGIN] Creating basic config file at: {config_file}")
            os.makedirs(os.path.dirname(config_file), exist_ok=True)

            basic_conf = '''
worker_processes ''' + str(config.get('worker_processes', 4)) + ''';
events {
    worker_connections ''' + str(config.get('max_connections', 1024)) + ''';
}

http {
    listen ''' + str(config.get('port', 80)) + ''';
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
'''
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(basic_conf)

        # 启动 Nginx
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Starting Nginx at port {config['port']}...")
        subprocess.Popen(
            [nginx_exe, "-c", config_file],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT
        )

        time.sleep(2)
        if get_nginx_status():
            print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx started successfully")
            return True
        else:
            print(f"[{datetime.now()}] [NGINX-PLUGIN] Failed to start Nginx")
            return False

    except Exception as e:
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Error starting Nginx: {e}")
        return False

def stop_nginx():
    """停止 Nginx"""
    if not get_nginx_status():
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx is not running")
        return True

    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "nginx.exe"],
            capture_output=True,
            text=True
        )

        if "nginx.exe" in result.stdout or "SUCCESS" in result.stdout:
            print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx stopped")
            return True
        else:
            print(f"[{datetime.now()}] [Nginx-plugin] Failed to stop Nginx")
            return False

    except Exception as e:
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Error stopping Nginx: {e}")
        return False

def reload_nginx():
    """重载 Nginx 配置"""
    if not get_nginx_status():
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx is not running")
        return False

    try:
        result = subprocess.run(
            ["nginx", "-s", "reload"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        print(f"[{datetime.now()}] [NGINX-PLUGIN] Reloaded Nginx configuration")
        return True

    except Exception as e:
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Error reloading Nginx: {e}")
        return False

def main():
    global running, config

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='R-Link Nginx Plugin')
    parser.add_argument('-c', '--config', help='Configuration file path')
    parser.add_argument('-p', '--port', type=int, help='Nginx 监听端口')
    parser.add_argument('--start', action='store_true', help='启动 Nginx')
    parser.add_argument('--stop', action='store_true', help='停止 Nginx')
    parser.add_argument('--reload', action='store_true', help='重载 Nginx 配置')
    parser.add_argument('--status', action='store_true', help='查看 Nginx 状态')

    args = parser.parse_args()

    # 加载配置
    if args.config:
        load_config(args.config)
    if args.port:
        config["port"] = args.port

    print(f"[{datetime.now()}] [NGINX-PLUGIN] ========================================")
    print(f"[{datetime.now()}] [NGINX-PLUGIN]   R-Link Nginx Plugin v1.0.0")
    print(f"[{datetime.now()}] [NGINX-PLUGIN] ========================================")
    print(f"[{datetime.now()}] [NGINX-PLUGIN] Port: {config['port']}")
    print(f"[{datetime.now()}] [NGINX-PLUGIN] Config: {args.config or 'default'}")
    print(f"[{datetime.now()}] [NGINX-PLUGIN] ========================================")

    # 执行命令
    if args.start:
        return start_nginx()
    elif args.stop:
        return stop_nginx()
    elif args.reload:
        return reload_nginx()
    elif args.status:
        status = "running" if get_nginx_status() else "stopped"
        print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx status: {status}")
        return 0
    else:
        # 作为守护进程运行
        # 首先启动 Nginx
        if not get_nginx_status():
            start_nginx()

        print(f"[{datetime.now()}] [NGINX-PLUGIN] Running in daemon mode...")

        try:
            while running:
                time.sleep(10)

                # 简单检查 nginx 是否还在运行
                if not get_nginx_status():
                    print(f"[{datetime.now()}] [NGINX-PLUGIN] Nginx process disappeared, exiting...")
                    running = False

        except KeyboardInterrupt:
            print(f"[{datetime.now()}] [NGINX-PLUGIN] Interrupted, shutting down...")
            stop_nginx()

    print(f"[{datetime.now()}] [NGINX-PLUGIN] Plugin stopped")

if __name__ == "__main__":
    main()
