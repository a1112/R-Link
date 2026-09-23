# NetBird 虚拟组网

R-Link 服务端通过 NetBird Public API 管理真实虚拟组网；它不自行运行 WireGuard、信令或中继服务。要形成跨设备网络，先部署 NetBird 控制面，再在每台设备安装 NetBird Agent。

1. 按 [官方自建指南](https://docs.netbird.io/selfhosted/selfhosted-quickstart) 部署 NetBird，或使用现有 NetBird 服务。
2. 创建具有组网管理权限的服务用户 PAT。为 R-Link 服务端设置 `R_LINK_NETBIRD_URL`（HTTPS 根地址）和 `R_LINK_NETBIRD_TOKEN`。
3. 打开 R-Link“虚拟组网”页面，创建分组及入网密钥。把显示一次的密钥安全交给目标设备，在设备上执行 `netbird up --management-url https://你的域名 --setup-key <密钥>`。
4. 在页面查看真实节点状态，管理分组、访问策略、网络资源和路由节点。用目标设备上的 `netbird status` 及实际网络访问验证连通性。

服务端环境变量、API 范围、认证和限制见[组网部署说明](../../docs/server-implementation-20260922.md#虚拟组网部署和使用)。原演示目录的批处理脚本仅用于安装、启动或查看本机 Agent；不要把本机 Agent 当成服务端控制面。
