# Core 集成验证记录（2026-10-19）

本轮将 BridgeProxy 引擎抽为 `bridgeproxy-core`，通过 `r-link-core` 原生适配器和 R-Link 服务端适配器接入，并提供“网络出口与代理”十个功能页。架构和运行方法见[核心架构](core-architecture.md)及[接入说明](bridgeproxy-core.md)。

## 已通过的检查

| 范围 | 结果 |
| --- | --- |
| BridgeProxy Rust workspace | Core 99 项、GUI 4 项通过；原有交互托盘测试 1 项忽略 |
| BridgeProxy 构建 | 独立 Core、GUI release 构建及无 desktop feature 编译通过 |
| BridgeProxy 实例验证 | 隔离数据目录运行真实 Core，八组 API 回归通过，覆盖快照、能力清单、配置、原子规则、启停、CONNECT 和凭据轮换 |
| BridgeProxy 资源与打包 | 六项离线脚本检查通过，Core 和 GUI 分别生成便携 ZIP、独立校验和；Core 源码包解包至工作区外，资源及许可证完整，独立离线 release 编译检查通过 |
| R-Link 原生 Core | 9 项通过，含六项真实 HTTP 客户端回归；真实 Core 的 Windows DPAPI、宿主身份及只读权限检查通过 |
| R-Link Tauri | 36 项通过；原有云端人工探测 1 项忽略 |
| R-Link 前端 | 272 项 Vitest、12 项窗口脚本测试及 TypeScript/生产构建通过 |
| R-Link 服务端 | 全量 446 项通过、2 项跳过；最后收紧 Docker 复制范围后，部署/NAS 29 项再次通过，包含新增私有文件边界检查 |
| 浏览器检查 | 十个功能页及 480px 窄屏布局通过，无页面异常或横向溢出 |

真实 API 验证使用本轮专用实例；浏览器布局检查使用固定模拟响应。没有为验证启用用户系统代理、应用代理或 TUN，也没有执行驱动安装、提权、节点升级安装或远端部署。这些需要实际使用时按 Core 的本机流程确认。服务端可管理的目标始终是其所在机器的回环 Core。

## 持续验证

R-Link CI 的触发范围包含独立 crate、共享合同和部署文件，Windows job 分别验证 `r-link-core` 和 Tauri。BridgeProxy 保持独立 CI、构建和打包流程。两个仓库均在本地 `codex/` 功能分支提交，本轮未推送或发布。

Core 和 GUI 的源码版本本轮仍为 0.6.1，便携包属于本地集成构建。接入应以 capabilities 等实际接口为准，不以旧版同名版本号判断支持。
