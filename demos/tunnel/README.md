# 内网穿透演示

## FRP - 快速反向代理

### 什么是 FRP

FRP (Fast Reverse Proxy) 是一个高性能的反向代理应用，用于内网穿透。

### 架构

```
                 ┌─────────────────┐
                 │     FRP Server  │
                 │   (有公网IP)     │
                 └────────┬────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────┴─────┐ ┌───┴────┐ ┌───┴────┐
        │ FRP Client│ │FRP C...│ │FRP C...│
        │  (内网)    │ │ (内网)  │ │ (内网)  │
        └───────────┘ └────────┘ └────────┘
```

### 服务端配置 (frps.ini)

```ini
[common]
bind_port = 7000          # 绑定端口
dashboard_port = 7500     # 仪表板端口
dashboard_user = admin    # 仪表板用户
dashboard_pwd = admin     # 仪表板密码
token = your_token        # 认证令牌
vhost_http_port = 80      # HTTP 代理端口
vhost_https_port = 443    # HTTPS 代理端口
```

### 客户端配置 (frpc.ini)

```ini
[common]
server_addr = x.x.x.x     # 服务器 IP
server_port = 7000        # 服务器端口
token = your_token        # 认证令牌

# SSH 穿透示例
[ssh]
type = tcp
local_ip = 127.0.0.1
local_port = 22
remote_port = 6000

# Web 服务穿透示例
[web]
type = http
local_ip = 127.0.0.1
local_port = 8080
custom_domains = yourdomain.com
```

### 使用方法

```bash
# 服务端启动
./frps -c frps.ini

# 客户端启动
./frpc -c frpc.ini

# 访问内网服务
ssh -p 6000 user@server_ip
```

## 二进制文件使用

将编译好的二进制文件放置在 `../../binaries/tunnel/` 目录：
- `frps.exe` / `frps` (服务端)
- `frpc.exe` / `frpc` (客户端)

## P2P 连接

P2P 功能可以通过集成 WebRTC 实现，参考 `streaming/README.md` 中的 WebRTC 部分实现。

NetBird 也支持 P2P 直连，参考 `networking/README.md`。
