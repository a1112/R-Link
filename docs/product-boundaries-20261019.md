# R-Link 与 BridgeProxy 产品分工

决策日期：2026-10-19。优先用户是个人与小团队，当前网络桥需求是共享代理与网络出口。

本决策已进一步落实为独立核心与完整功能集成，当前实现以[核心架构](core-architecture.md)为准；下文保留首次同步时的产品分工依据。

## 产品定位

采用独立产品、统一入口、独立发版。R-Link 提供网络管理平台，BridgeProxy 保留可独立安装和运行的 Windows 工具。用户可按需选择产品，网络引擎与管理平台分别升级和恢复。

| 模块 | 职责 | 状态与配置的所有者 |
| --- | --- | --- |
| R-Link | 设备清单、拓扑、账号权限、SSH、文件及统一管理入口 | R-Link 服务端及桌面客户端 |
| R-Link Fabric | 设备登记、WireGuard 三层组网、候选交换、打洞、中转和路径恢复 | Fabric 控制面与本机 Agent |
| BridgeProxy | 出口共享、多级代理、反向隧道、分流、系统代理、应用代理和 TUN | 独立 BridgeProxy 进程及其本机配置 |

BridgeProxy 当前提供反向代理隧道和 IP TUN，不提供以太网二层桥接或 ARP/DHCP 广播透传。Fabric 当前不提供 LAN 子网网关、默认出口或全局 DNS。这些能力如需增加，应另行定义需求与验收标准。

## 集成接口与生命周期

后续桌面集成采用：

```text
R-Link 界面 → Tauri 原生后端 → BridgeProxy 127.0.0.1 控制 API v1
```

- BridgeProxy 控制 API 拒绝带 Origin 的请求，由原生后端调用；浏览器版和部署在 NAS/Linux 的 R-Link 服务端不直接代表 Windows 本机执行控制。
- 凭据保存在原生层，状态只返回所需的脱敏字段。配置、配对身份和凭据各自管理；R-Link 账号不会自动取得 BridgeProxy 的控制权限。
- BridgeProxy 是自身配置和网络接管的唯一写入者。集成使用其现有 API、配置 revision 和 operation 状态，不直接修改受保护配置文件。
- 复用已运行实例；R-Link 退出不终止用户独立运行的 BridgeProxy。TUN 提权、配对双方确认和安装升级沿用 BridgeProxy 的本机确认流程。
- 系统代理、应用代理和 TUN 分别显示实际状态。应用代理环境是持久设置，停止代理服务不等同于恢复环境。
- API 请求受理或 operation 成功不代表流量可用；链路认证、核心状态、实际网卡和业务探测分别作为证据。

后续若增加跨设备控制，需要独立设计授权、审计与故障恢复。当前本机控制接口继续只监听回环地址。

## 分期路线

1. **只读接入：** 在 R-Link 展示 BridgeProxy 版本、服务与链路状态、采样时间，提供打开独立客户端的入口；识别未安装、未运行、API 禁用、版本不兼容及不支持的平台。
2. **受限控制：** 接入启停、上游选择和诊断，使用既有异步操作与配置版本检查；保留草稿冲突、配对和权限检查，分别呈现操作结果与实际运行状态。

首次同步仅确认产品与接口边界。后续同日开发已抽离 BridgeProxy Core，并实现 R-Link Core 适配器、版本化 API 与功能界面，详见[当前接入说明](bridgeproxy-core.md)。

R-Link 的 R-SDK read bridge 保持默认关闭。该接口仍为候选实现，设备发现操作禁用，独立审查仍是发布前提；不能将其视为现成的生产集成基础。详见 [R-SDK 读取边界](interop-read-adapter.md)。

## 核查基线

- R-Link 远端主线：`c7d45379038010face712f20f84d67f4e6b0e81b`。
- BridgeProxy：`338412f24731f005f00dd2c860d71bd1b2189f77`，版本 0.6.1。
- BridgeProxy 接口依据：[API 文档](https://github.com/a1112/bridgeproxy-windows/blob/338412f24731f005f00dd2c860d71bd1b2189f77/docs/API.md)及其控制服务实现；产品许可证和依赖清单继续由各产品维护。

本轮代码整合与验证结果见[同步记录](sync-20261019.md)。
