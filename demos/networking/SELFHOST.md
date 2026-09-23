# NetBird 自建控制面

本仓库不打包或部署 NetBird 控制面。请使用[NetBird 官方自建快速入门](https://docs.netbird.io/selfhosted/selfhosted-quickstart)生成当前版本的服务配置，并以官方说明为准。旧版分散服务的端口、Docker Compose 和安装脚本已失效，因此不在这里复刻。

完成部署后，在 NetBird 创建服务用户 Personal Access Token。R-Link 通过 `R_LINK_NETBIRD_URL` 和 `R_LINK_NETBIRD_TOKEN` 访问管理 API，具体步骤见[服务端部署文档](../../docs/server-implementation-20260922.md#虚拟组网部署和使用)。至少准备两台已安装 NetBird Agent 的设备，入网后从设备之间验证虚拟 IP 连通性及访问策略；R-Link 页面上的“管理端在线”不能证明 P2P 直连或目标网段可达。
