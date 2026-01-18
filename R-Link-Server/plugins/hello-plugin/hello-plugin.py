#!/usr/bin/env python3
"""
R-Link Hello World 测试插件
一个简单的演示插件，展示插件系统的基本功能
"""

import argparse
import json
import os
import sys
import time
import signal
from datetime import datetime

# 全局变量
running = True
config = {
    "message": "Hello from R-Link!",
    "interval": 5
}

def signal_handler(signum, frame):
    """处理关闭信号"""
    global running
    print(f"[{datetime.now()}] [HELLO-PLUGIN] Received signal {signum}, shutting down...")
    running = False

def load_config(config_path):
    """加载配置文件"""
    global config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            config.update(loaded)
            print(f"[{datetime.now()}] [HELLO-PLUGIN] Config loaded: {config}")
    except Exception as e:
        print(f"[{datetime.now()}] [HELLO-PLUGIN] Failed to load config: {e}")

def save_config(config_path):
    """保存配置文件"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"[{datetime.now()}] [HELLO-PLUGIN] Config saved")
    except Exception as e:
        print(f"[{datetime.now()}] [HELLO-PLUGIN] Failed to save config: {e}")

def handle_command(cmd):
    """处理自定义命令"""
    if cmd == "ping":
        return {"status": "pong", "message": config["message"]}
    elif cmd == "info":
        return {
            "name": "hello-plugin",
            "version": "1.0.0",
            "description": "Hello World 测试插件",
            "config": config
        }
    else:
        return {"error": "Unknown command", "command": cmd}

def main():
    global running, config

    # 注册信号处理
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='R-Link Hello Plugin')
    parser.add_argument('-c', '--config', help='Configuration file path')
    parser.add_argument('-m', '--message', help='Custom message')
    parser.add_argument('-i', '--interval', type=int, help='Update interval (seconds)')
    parser.add_argument('--message-override', help='Override message from config')

    args = parser.parse_args()

    # 加载配置文件
    if args.config:
        load_config(args.config)

    # 命令行参数覆盖
    if args.message:
        config["message"] = args.message
    if args.interval:
        config["interval"] = args.interval

    print(f"[{datetime.now()}] [HELLO-PLUGIN] ========================================")
    print(f"[{datetime.now()}] [HELLO-PLUGIN]   R-Link Hello World Plugin v1.0.0")
    print(f"[{datetime.now()}] [HELLO-PLUGIN] ========================================")
    print(f"[{datetime.now()}] [HELLO-PLUGIN] Message: {config['message']}")
    print(f"[{datetime.now()}] [HELLO-PLUGIN] Interval: {config['interval']} seconds")
    print(f"[{datetime.now()}] [HELLO-PLUGIN] Config: {args.config}")
    print(f"[{datetime.now()}] [HELLO-PLUGIN] ========================================")

    # 主循环
    counter = 0
    interval = config["interval"]

    try:
        while running:
            print(f"[{datetime.now()}] [HELLO-PLUGIN] [{counter}] {config['message']}")
            sys.stdout.flush()

            # 等待间隔，同时检查运行状态
            for _ in range(interval * 10):
                if not running:
                    break
                time.sleep(0.1)

            if not running:
                break

            counter += 1

    except Exception as e:
        print(f"[{datetime.now()}] [HELLO-PLUGIN] Error: {e}")

    print(f"[{datetime.now()}] [HELLO-PLUGIN] Plugin stopped")

if __name__ == "__main__":
    main()
