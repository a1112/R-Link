#!/bin/bash
# NetBird 自建服务端 - 快速部署脚本
# 适用于: Ubuntu 20.04+, Debian 11+

set -e

echo "=========================================="
echo "NetBird 自建服务端 - 快速部署"
echo "=========================================="
echo ""

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 配置变量
read -p "请输入域名 (如: netbird.example.com): " DOMAIN
read -p "请输入邮箱 (用于 Let's Encrypt 证书): " EMAIL

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "错误: 域名和邮箱不能为空"
    exit 1
fi

# 生成随机密码
RELAY_SECRET=$(openssl rand -hex 16)
TURN_PASSWORD=$(openssl rand -hex 16)

# 安装 Docker
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 安装 docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "安装 docker-compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# 创建部署目录
DEPLOY_DIR="/opt/netbird"
mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# 创建 setup.env
cat > setup.env << EOF
# 域名配置
NETBIRD_DOMAIN=$DOMAIN
NETBIRD_LETSENCRYPT_EMAIL=$EMAIL

# 管理配置
NETBIRD_MGMT_SINGLE_ACCOUNT_MODE_DOMAIN=$DOMAIN
NETBIRD_MGMT_DNS_DOMAIN=netbird.selfhosted
NETBIRD_MGMT_API_PORT=33073
NETBIRD_MGMT_API_ENDPOINT=https://$DOMAIN:33073

# Signal 配置
NETBIRD_SIGNAL_PORT=10000

# Relay 配置
NETBIRD_RELAY_DOMAIN=$DOMAIN
NETBIRD_RELAY_PORT=33080
NETBIRD_RELAY_ENDPOINT=rel://$DOMAIN:33080
NETBIRD_RELAY_AUTH_SECRET=$RELAY_SECRET

# TURN 配置
TURN_DOMAIN=$DOMAIN
TURN_USER=self
TURN_PASSWORD=$TURN_PASSWORD
TURN_MIN_PORT=49152
TURN_MAX_PORT=65535

# 数据库 (使用 SQLite，简单部署)
NETBIRD_STORE_CONFIG_ENGINE=sqlite

# 禁用匿名指标
NETBIRD_DISABLE_ANONYMOUS_METRICS=true

# 镜像版本
NETBIRD_DASHBOARD_TAG=latest
NETBIRD_SIGNAL_TAG=latest
NETBIRD_MANAGEMENT_TAG=latest
COTURN_TAG=latest
NETBIRD_RELAY_TAG=latest
EOF

# 创建 docker-compose.yml
cat > docker-compose.yml << EOF
version: '3.8'

services:
  dashboard:
    image: netbirdio/dashboard:latest
    container_name: netbird-dashboard
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      - NETBIRD_MGMT_API_ENDPOINT=https://\$NETBIRD_DOMAIN:33073
      - NETBIRD_MGMT_GRPC_API_ENDPOINT=https://\$NETBIRD_DOMAIN:33073
      - AUTH_AUDIENCE=netbird
      - AUTH_CLIENT_ID=netbird-client
      - AUTH_CLIENT_SECRET=netbird-secret
      - AUTH_AUTHORITY=https://\$NETBIRD_DOMAIN:443
      - USE_AUTH0=false
      - AUTH_SUPPORTED_SCOPES=openid profile email
      - AUTH_REDIRECT_URI=https://\$NETBIRD_DOMAIN/callback
      - AUTH_SILENT_REDIRECT_URI=https://\$NETBIRD_DOMAIN/silent-callback
      - NETBIRD_TOKEN_SOURCE=accessToken
      - LETSENCRYPT_DOMAIN=\$NETBIRD_DOMAIN
      - LETSENCRYPT_EMAIL=\$NETBIRD_LETSENCRYPT_EMAIL
    volumes:
      - netbird-letsencrypt:/etc/letsencrypt/
      - ./caddy_data:/data
      - ./caddy_config:/config

  signal:
    image: netbirdio/signal:latest
    container_name: netbird-signal
    restart: unless-stopped
    depends_on:
      - dashboard
    ports:
      - "10000:80"
    command: [
      "--cert-file", "/etc/letsencrypt/live/\$NETBIRD_DOMAIN/fullchain.pem",
      "--cert-key", "/etc/letsencrypt/live/\$NETBIRD_DOMAIN/privkey.pem",
      "--log-file", "console",
      "--port", "80"
    ]
    volumes:
      - netbird-letsencrypt:/etc/letsencrypt:ro
      - netbird-signal:/var/lib/netbird

  management:
    image: netbirdio/management:latest
    container_name: netbird-management
    restart: unless-stopped
    depends_on:
      - dashboard
    ports:
      - "33073:443"
    command: [
      "--port", "443",
      "--log-file", "console",
      "--log-level", "info",
      "--disable-anonymous-metrics=true",
      "--single-account-mode-domain=\$NETBIRD_MGMT_SINGLE_ACCOUNT_MODE_DOMAIN",
      "--dns-domain=\$NETBIRD_MGMT_DNS_DOMAIN"
    ]
    volumes:
      - netbird-mgmt:/var/lib/netbird
      - netbird-letsencrypt:/etc/letsencrypt:ro
      - ./management.json:/etc/netbird/management.json

  relay:
    image: netbirdio/relay:latest
    container_name: netbird-relay
    restart: unless-stopped
    environment:
      - NB_LOG_LEVEL=info
      - NB_LISTEN_ADDRESS=:33080
      - NB_EXPOSED_ADDRESS=rel://\$NETBIRD_DOMAIN:33080
      - NB_AUTH_SECRET=\$NETBIRD_RELAY_AUTH_SECRET
    ports:
      - "33080:33080"

  coturn:
    image: instrumentisto/coturn:latest
    container_name: netbird-coturn
    restart: unless-stopped
    network_mode: host
    command:
      - -n
      - --log-file=stdout
      - --external-ip=\$(curl -s ifconfig.me)
      - --listening-port=3478
      - --min-port=49152
      - --max-port=65535
      - --user=\$TURN_USER:\$TURN_PASSWORD
      - --realm=\$TURN_DOMAIN
      - --fingerprint
      - --lt-cred-mech

volumes:
  netbird-letsencrypt:
  netbird-signal:
  netbird-mgmt:
EOF

# 创建 management.json
cat > management.json << EOF
{
  "StunURI": "turn:\$TURN_USER:\$TURN_PASSWORD@\$TURN_DOMAIN:3478?transport=udp",
  "TurnAddress": "\$TURN_DOMAIN:3478",
  "RelayAddresses": ["\$NETBIRD_RELAY_ENDPOINT"],
  "SignalURI": "https://\$NETBIRD_DOMAIN:10000"
}
EOF

# 处理环境变量替换
source setup.env
envsubst < docker-compose.yml > docker-compose.yml.tmp
mv docker-compose.yml.tmp docker-compose.yml

envsubst < management.json > management.json.tmp
mv management.json.tmp management.json

echo ""
echo "=========================================="
echo "配置完成！"
echo "=========================================="
echo "域名: $DOMAIN"
echo "邮箱: $EMAIL"
echo ""
echo "启动服务..."
docker-compose up -d

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "访问方式:"
echo "  Web UI: https://$DOMAIN"
echo "  API: https://$DOMAIN:33073"
echo ""
echo "查看日志:"
echo "  docker-compose logs -f"
echo ""
echo "客户端配置:"
echo "  管理面板: https://$DOMAIN"
echo "  Setup Key 在面板中创建后配置到客户端"
