# NetBird 自建服务端指南

## 方式一：快速部署脚本 (推荐)

### 1. 服务器要求
- Linux 系统 (Ubuntu 20.04+ / Debian 11+)
- 1 CPU, 2GB 内存
- 有公网 IP
- 域名指向服务器 (可选，但推荐)

### 2. 开放端口
```bash
# 防火墙配置
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 3478/udp
sudo ufw allow 33073/tcp
sudo ufw allow 33080/tcp
sudo ufw allow 10000/tcp
sudo ufw allow 49152:65535/udp
```

### 3. 运行部署脚本
```bash
# 上传 deploy-netbird.sh 到服务器
chmod +x deploy-netbird.sh
sudo ./deploy-netbird.sh
```

### 4. 访问管理面板
```
https://your-domain.com
```

首次访问会创建管理员账户。

---

## 方式二：官方一键部署脚本

### 一键命令
```bash
export NETBIRD_DOMAIN=netbird.example.com
curl -fsSL https://github.com/netbirdio/netbird/releases/latest/download/getting-started.sh | bash
```

### 选择部署选项
```
? Select the deployment type:
  ▸ Caddy (reverse proxy, automatic HTTPS)
    Traefik (reverse proxy, automatic HTTPS)
    Nginx (reverse proxy, manual HTTPS)
    None (bring your own reverse proxy)
```

推荐选择 **Caddy**，自动配置 HTTPS。

---

## 客户端配置

### Windows 客户端
```batch
# 安装客户端
cd J:\R-Link\binaries\networking
netbird.exe service install

# 连接到自建服务器
netbird.exe up --setup-key <YOUR_SETUP_KEY> --management-url https://your-domain.com:33073
```

### 配置文件 (持久化)
创建 `%USERPROFILE%\.config\netbird\config.json`:
```json
{
  "ManagementURL": "https://your-domain.com:33073",
  "AdminURL": "https://your-domain.com:33073",
  "SingleAccount": true
}
```

### 常用命令
```batch
# 连接
netbird.exe up

# 查看状态
netbird.exe status

# 列出所有对等节点
netbird.exe list

# 断开连接
netbird.exe down
```

---

## 服务端管理

### 查看日志
```bash
cd /opt/netbird
docker-compose logs -f
```

### 重启服务
```bash
cd /opt/netbird
docker-compose restart
```

### 更新版本
```bash
cd /opt/netbird
docker-compose pull
docker-compose up -d
```

### 备份数据
```bash
# SQLite 数据库位置
docker exec netbird-management cp /var/lib/netbird/management-store.db /backup/
docker cp netbird-management:/backup/management-store.db ./backup/
```

---

## 服务端架构说明

```
┌─────────────────────────────────────────────────────────┐
│                    NetBird 服务端                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   │
│  │  Dashboard  │   │ Management  │   │   Signal    │   │
│  │  (Web UI)   │   │ (REST API)  │   │  (WebRTC)   │   │
│  │   :80/443   │   │   :33073    │   │   :10000    │   │
│  └─────────────┘   └─────────────┘   └─────────────┘   │
│                                                          │
│  ┌─────────────┐   ┌─────────────┐                      │
│  │    Relay    │   │   Coturn    │                      │
│  │  (TURN 中继) │   │ (STUN/TURN) │                      │
│  │   :33080    │   │   :3478     │                      │
│  └─────────────┘   └─────────────┘                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
                           │
                           │ WireGuard + P2P
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   客户端 A (Windows)  客户端 B (Linux)  客户端 C (手机)
```

### 组件说明
| 组件 | 端口 | 说明 |
|------|------|------|
| Dashboard | 80/443 | Web 管理界面 |
| Management | 33073 | REST API + gRPC |
| Signal | 10000 | WebRTC 信令服务 |
| Relay | 33080 | 中继服务器 (P2P 失败时使用) |
| Coturn | 3478 | STUN/TURN 服务器 (NAT 穿透) |
