#!/bin/bash
# R-Link 快速启动脚本 (Linux/macOS)

echo "======================================"
echo "R-Link - 集成连接工具"
echo "======================================"
echo ""
echo "选择要启动的功能:"
echo ""
echo "[1] Sunshine - 游戏串流服务器"
echo "[2] NetBird - 远程组网"
echo "[3] Rclone - 云存储同步"
echo "[4] FRP Server - 内网穿透服务端"
echo "[5] FRP Client - 内网穿透客户端"
echo "[0] 退出"
echo ""

read -p "请输入选择: " choice

case $choice in
    1)
        if [ -f "../../binaries/streaming/sunshine" ]; then
            echo "启动 Sunshine..."
            ../../binaries/streaming/sunshine
        else
            echo "错误: 找不到 sunshine 二进制文件"
        fi
        ;;
    2)
        if [ -f "../../binaries/networking/netbird" ]; then
            echo "启动 NetBird..."
            ../../binaries/networking/netbird up
        else
            echo "错误: 找不到 netbird 二进制文件"
        fi
        ;;
    3)
        if [ -f "../../binaries/storage/rclone" ]; then
            echo "列出 Rclone 配置..."
            ../../binaries/storage/rclone listremotes
        else
            echo "错误: 找不到 rclone 二进制文件"
        fi
        ;;
    4)
        if [ -f "../../binaries/tunnel/frps" ]; then
            echo "启动 FRP 服务端..."
            ../../binaries/tunnel/frps -c tunnel/frps.ini
        else
            echo "错误: 找不到 frps 二进制文件"
        fi
        ;;
    5)
        if [ -f "../../binaries/tunnel/frpc" ]; then
            echo "启动 FRP 客户端..."
            ../../binaries/tunnel/frpc -c tunnel/frpc.ini
        else
            echo "错误: 找不到 frpc 二进制文件"
        fi
        ;;
    0)
        echo "退出"
        ;;
    *)
        echo "无效选择"
        ;;
esac
