# R-Link

大型集成连接工具 - 集成 FRP, P2P, 远程, WebDav, 远程组网, 串流等功能。

## 项目结构

```
R-Link/
├── submodules/      # Git 子模块 (源代码)
├── binaries/        # 二进制文件目录
├── demos/           # 最小化功能演示
├── docs/            # 文档
└── README.md        # 本文件
```

## 集成项目

### 串流
- **Sunshine** - 游戏串流服务器 (支持 NVIDIA/AMD/Intel 显卡)
- **Moonlight** - 游戏串流客户端 (多平台支持)
- **WebRTC** - 实时通信协议

### 远程组网
- **NetBird** - 零配置 WireGuard VPN (类似 Tailscale)

### 远程桌面
- **RustDesk** - 自建远程桌面/控制

### 内网穿透
- **FRP** - 快速反向代理

### 云存储/文件传输
- **Rclone** - 支持多种云存储和 WebDav

## 使用说明

每个子模块的使用方式请参考各项目的官方文档。

## 开发

```bash
# 克隆项目及子模块
git clone --recursive https://github.com/a1112/R-Link.git

# 如果已经克隆，拉取子模块
git submodule update --init --recursive
```

## 许可证

本项目集成各开源项目，请遵循各自的许可证。
