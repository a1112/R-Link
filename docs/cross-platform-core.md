# Core 跨平台范围

两个产品保持独立核心、版本化 API 和独立发版。R-Link 桌面在 Windows、Linux、macOS 原生连接本机 BridgeProxy Core；Web 版通过 R-Link 服务端连接服务端所在机器的 Core。

## 目标与功能

| 平台/架构 | Core 与 R-Link 原生接入 | 原生流量接管 | 节点 EXE 更新 |
| --- | --- | --- | --- |
| Windows x64 | 保留实现，本机回归 | TUN、系统代理、持久应用代理 | 保留原 Windows 本机确认流程 |
| Linux x64 / ARM64 | 已实现，纳入目标平台 CI | 本轮未提供 | 不提供 |
| macOS Intel / Apple Silicon | 已实现，纳入目标平台 CI | 本轮未提供 | 不提供 |

各平台共享 HTTP/SOCKS 代理、上游出站、反向隧道、发现配对、链路、分流、连接流量、诊断日志、异步操作与控制 API。Linux/macOS 的 TUN、系统代理及持久应用代理后续仍需各自实现网卡、权限、备份恢复和系统状态观测，不能将 Windows 设置直接照搬。

Core 在 capabilities 中声明平台和能力，为不支持的写入返回 501；配置候选也不能借通用 PATCH 绕过平台限制。R-Link 的流量接管按钮同时检查 feature 和 route.available，所有命令在提交前核对当前清单。旧快照、缺失能力或未知路由不能当成已支持。

若导入的 Windows 配置仍开启 TUN 或系统代理，Unix 的“流量接管”页可明确清除这些配置并保存；此操作不应用配置、不启动服务，也不尝试恢复另一系统的网络设置。

## 本机身份和存储

- Windows 保留 DPAPI 及宿主 PID/FILETIME 核验。
- Linux/macOS 的 Core 数据目录为当前有效用户拥有的 0700，私有文件为 0600；拒绝符号链接、硬链接及不符合权限的文件。凭据标记 `unix-owner-only`，这是文件权限保护，不宣称经过 DPAPI 或 Keychain 加密。
- Linux 核对 `/proc` 的进程启动标识和用户，macOS 核对 libproc 返回的启动时间与有效用户，避免复用 PID 后连接到其他宿主。
- R-Link 连接授权保留在进程中，Unix 保留已授权数据目录的文件描述符，凭据轮换后在下一次请求读取；账号切换撤销授权。两端必须使用同一系统用户。

启动、数据目录选择和服务端环境变量见[接入说明](bridgeproxy-core.md)。Linux 的服务端原生部署可以使用本机 Linux Core；Docker 的回环地址仍属于容器自身，不会自动获得宿主机 Core。不要为接入将控制 API 监听到公网。

Core 正常退出或收到 SIGTERM/SIGINT 时会停止子引擎。Linux 另外设置父进程死亡信号；macOS 强制 SIGKILL 无法执行退出清理，服务管理器需要处理整个服务进程组。关闭 R-Link 管理界面不会停止独立 Core。

## 构建与持续验证

R-Link 的 `desktop-unix` CI 分别在 Linux x64/ARM64、macOS Intel/Apple Silicon 原生 runner 上执行独立 `r-link-core` 测试、Tauri 测试和客户端编译。BridgeProxy 在相应目标准备固定版本、核验 SHA-256 的引擎资源，独立构建 Core 与客户端，运行隔离 API/代理 smoke 并分别打包。

Linux 桌面依赖 WebKitGTK 4.1、OpenSSL 和托盘相关库；macOS 配置最低版本按 Tauri 2 的当前[官方前置条件](https://v2.tauri.app/start/prerequisites/)设为 10.15。GitHub 原生 runner 的架构标签依据[官方 runner 列表](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)，不将交叉编译当作原生运行验证。

当前开发机器是 Windows。本轮本机检查不能证明 Linux/macOS 原生编译、真实网络、桌面交互、签名或公证已通过；这些须以对应 CI 及目标机器验收为准。CI 文件已纳入源码，远端执行和发布需实际推送后发生。Windows 原有便携包也不能在 Unix 上运行，应使用对应平台构建。

本轮本机已通过：

| 检查 | 结果 |
| --- | --- |
| R-Link 原生 Core / Tauri | 11 项 / 36 项通过 |
| R-Link 前端 | 277 项及窗口脚本 12 项通过，TypeScript/生产构建通过 |
| 新 Core 与 R-Link 联调 | 在隔离目录启动真实 Core，原生 DPAPI/宿主身份、能力/快照/文档读取、只读权限和脱敏检查通过 |
| BridgeProxy Core | Windows release 构建、102 项 Rust 测试及真实隔离 HTTP 代理 smoke 通过；静态 OpenAPI 字段完整性与实际 SAS 脱敏分别回归 |
| BridgeProxy 独立 GUI | Windows release 编译检查通过；新增 Unix X11/Wayland、系统字体和能力门控 |
| 脚本与合同 | 9 项离线资源、OpenAPI、Core/GUI 独立打包检查通过；四个 Unix 目标的官方引擎归档和 SHA-256 已核对 |

Unix 专属的权限、链接、目录替换和进程身份测试已编写，随原生 CI 执行。之前 Windows 集成验证见[记录](core-integration-validation-20261019.md)。

Android/iOS 本轮仅可通过 Web 入口使用服务端目标，未新增移动端本机 Core 管理、VPN 权限或应用商店发行流程。
