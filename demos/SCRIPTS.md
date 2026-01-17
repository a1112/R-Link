# R-Link 脚本说明

## 快速开始

```batch
cd J:\R-Link\demos
control.bat
```

## 脚本目录结构

```
demos/
├── control.bat           # 主控制面板 (推荐使用)
├── start.bat             # 快速启动菜单
│
├── streaming/            # 游戏串流 (Sunshine)
│   ├── start.bat         # 启动 Sunshine
│   ├── stop.bat          # 停止 Sunshine
│   └── status.bat        # 查看状态
│
├── networking/           # 远程组网 (NetBird)
│   ├── start.bat         # 连接到 NetBird
│   ├── stop.bat          # 断开连接
│   ├── status.bat        # 查看状态和对等节点
│   └── install.bat       # 安装为 Windows 服务
│
├── storage/              # 云存储 (Rclone)
│   ├── config.bat        # 配置向导
│   ├── list-remotes.bat  # 列出已配置的远程
│   ├── ls.bat            # 浏览远程文件
│   ├── copy.bat          # 复制文件
│   ├── sync.bat          # 同步文件
│   └── mount.bat         # 挂载为网盘
│
└── tunnel/               # 内网穿透 (FRP)
    ├── server-start.bat  # 启动 FRP 服务端
    ├── server-stop.bat   # 停止服务端
    ├── server-status.bat # 服务端状态
    ├── client-start.bat  # 启动 FRP 客户端
    ├── client-stop.bat   # 停止客户端
    └── client-status.bat # 客户端状态
```

## 各模块说明

### 1. 串流服务 (Sunshine)

| 脚本 | 功能 |
|------|------|
| `streaming/start.bat` | 启动 Sunshine 串流服务器 |
| `streaming/stop.bat` | 停止 Sunshine |
| `streaming/status.bat` | 查看运行状态 |

**访问地址**: http://localhost:47990

### 2. 远程组网 (NetBird)

| 脚本 | 功能 |
|------|------|
| `networking/install.bat` | 安装为 Windows 服务 (开机自启) |
| `networking/start.bat` | 连接到 NetBird 网络 |
| `networking/stop.bat` | 断开连接 |
| `networking/status.bat` | 查看状态和对等节点列表 |

**连接方式**:
- 官方服务器 (免费)
- 自建服务器

### 3. 云存储 (Rclone)

| 脚本 | 功能 |
|------|------|
| `storage/config.bat` | 运行配置向导 |
| `storage/list-remotes.bat` | 列出所有已配置的远程存储 |
| `storage/ls.bat` | 浏览远程文件 |
| `storage/copy.bat` | 复制文件 (本地↔远程) |
| `storage/sync.bat` | 同步文件 (危险，会删除目标多余文件) |
| `storage/mount.bat` | 挂载为网盘 (需要 WinFsp) |

**支持的服务**: Google Drive, Dropbox, OneDrive, WebDav, SFTP, FTP 等

### 4. 内网穿透 (FRP)

| 脚本 | 功能 |
|------|------|
| `tunnel/server-start.bat` | 启动 FRP 服务端 (需要有公网 IP) |
| `tunnel/server-stop.bat` | 停止服务端 |
| `tunnel/server-status.bat` | 服务端状态 |
| `tunnel/client-start.bat` | 启动 FRP 客户端 (内网机器) |
| `tunnel/client-stop.bat` | 停止客户端 |
| `tunnel/client-status.bat` | 客户端状态 |

**配置文件**:
- 服务端: `tunnel/frps.ini`
- 客户端: `tunnel/frpc.ini`

## 常见使用场景

### 场景 1: 局域网游戏串流
```batch
cd demos\streaming
start.bat
# 在 Moonlight 客户端输入 Sunshine 服务器 IP
```

### 场景 2: 远程组网 + 游戏串流
```batch
# 1. 启动 NetBird 组网
cd demos\networking
start.bat

# 2. 启动 Sunshine
cd ..\streaming
start.bat

# 3. 在远程设备的 Moonlight 中连接
```

### 场景 3: 内网穿透访问远程桌面
```batch
# 服务器端 (有公网 IP)
cd demos\tunnel
server-start.bat

# 客户端 (内网机器)
# 编辑 frpc.ini 配置 RDP 穿透
client-start.bat

# 从外网连接: mstsc /v:server_ip:3389
```

### 场景 4: 云存储备份
```batch
# 1. 配置云存储
cd demos\storage
config.bat

# 2. 同步文件
sync.bat
```
