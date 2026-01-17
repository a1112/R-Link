# 远程组网演示

## NetBird - 零配置 WireGuard VPN

### 什么是 NetBird

NetBird 是一个类似 Tailscale 的开源组网工具，基于 WireGuard 实现。

### 快速开始

```bash
# 安装 NetBird (需要先从 Releases 下载二进制文件)
# Windows: netbird.exe install
# Linux:   sudo netbird service install

# 连接到管理面板
netbird up

# 查看连接状态
netbird status

# 查看对等节点
netbird list
```

### 配置文件位置
- Windows: `%LOCALAPPDATA%\NetBird\config.json`
- Linux: `~/.config/netbird/config.json`
- macOS: `~/Library/Application Support/NetBird/config.json`

### 管理面板

自建管理面板需要配置：
1. 创建 NetBird 账户/管理服务
2. 配置客户端连接到自建服务器
3. 设置访问策略

### 自建服务端示例

参考 `submodules/netbird/` 中的部署文档：
```bash
# 使用 Docker 部署管理服务
cd submodules/netbird
docker compose up -d
```

## 二进制文件使用

将编译好的二进制文件放置在 `../../binaries/networking/` 目录：
- `netbird.exe` (Windows) / `netbird` (Linux/macOS)

## 最小化配置示例

```json
{
  "ManagementURL": "https://api.netbird.io",
  "AdminURL": "https://api.netbird.io",
  "PreSharedKey": ""
}
```
