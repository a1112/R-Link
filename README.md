# R-Link

连接工具管理平台，包含 React Web/Tauri 客户端、FastAPI 服务端，以及网络、存储、串流集成演示。

**R-Link-Web 已整合到本仓库的 `apps/r-link-web/`，后续开发统一在 R-Link 进行。** 原始快照与增量核对见 [迁移记录](docs/repository-consolidation/R-Link-Web/README.md)。

## 开发

需要 Node.js 22+、npm、Python 3.12+；桌面构建另需 Rust 和对应系统的 Tauri 构建工具。

```sh
npm run setup:web
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r R-Link-Server/requirements-test.txt
```

本地使用无需云账号或数据库配置，启动后直接进入管理界面。服务端默认只监听 `127.0.0.1`，检查客户端地址、Host 和浏览器来源。需要自定义 API 地址时，复制 `apps/r-link-web/.env.example` 为 `.env.local` 并设置 `VITE_API_BASE_URL`。

远程部署（包括通过反向代理提供服务）必须先设置随机的 `R_LINK_API_TOKEN`，再按需设置 `R_LINK_HOST`。在客户端“系统设置 → 服务访问”中填写相同密钥；密钥只保存在当前浏览器会话，并且只发送到配置的 API 地址。配置密钥后，本机请求也需提供密钥。远程访问应使用 HTTPS；这是单一服务操作员访问模式，没有云账号或用户角色。
```sh
# 已激活 Python 环境的终端
npm run dev:server
# 另一个终端
npm run dev
```

Web 地址为 `http://127.0.0.1:4322`，API 地址为 `http://127.0.0.1:8210`，API 文档在 `/docs`。Web 开发代理已连接 API；静态部署需配置反向代理或 `VITE_API_BASE_URL`。服务端 CORS 可通过 `R_LINK_CORS_ORIGINS` 设置允许的来源（逗号分隔）。`DEV=true` 启用服务端热重载。

SSH 使用服务端用户的 `~/.ssh/known_hosts` 校验主机密钥，也可通过 `R_LINK_SSH_KNOWN_HOSTS` 指定可信文件；连接必须提供目标主机的密码或私钥。多进程部署须设置相同的私有 `R_LINK_WS_TOKEN_SECRET`。

## 设备与托盘管理

统一设备管理支持类型、平台、标签、备注和服务入口，自动同步 NetBird 节点并显示带时效的组网状态，可关联网关后的设备和明确撤销入网。安装好的客户端可在“系统设置 → 服务访问”填写云端服务地址；各设备安装 NetBird，手机也可通过浏览器管理。云端配置、各平台安装、网关接入和升级备份见[全部设备接入说明](docs/device-management-20261003.md)。

设备列表支持添加、编辑、删除和持久保存地址，按需从服务端检测指定 TCP 端口，并可将地址带入 SSH 连接表单。默认数据库为 `R-Link-Server/config/devices.sqlite3`，可用 `R_LINK_DEVICES_DB` 指定位置；不保存设备密码或私钥。检测结果带时间，不代表整台设备健康。仪表盘按网卡显示真实流量采样，不再展示虚构的隧道数量。

桌面版提供系统托盘：单击恢复窗口，右键打开仪表盘、设备管理、设备连接视图、SSH、插件管理和设置，或隐藏窗口、退出。默认关闭窗口后驻留；在“系统设置 → 通用设置”或托盘菜单切换，设置在系统应用配置目录的 `desktop.json` 中保存。重复启动会恢复已有窗口。切换管理页和隐藏窗口会保留当前 SSH 会话；退出客户端会断开客户端连接，不停止独立服务端和插件。

Windows 本机完成依赖安装与桌面构建后，可双击 `Start-R-Link.cmd`，自动启动或复用本地服务，再打开客户端。自定义程序位置使用 `scripts/start-local.ps1 -DesktopPath <exe>`。详见[启动与真实界面修复记录](docs/desktop-real-ui-20260919.md)。

[设备网络与托盘审查记录](docs/network-tray-audit-20260919.md)。

## 共享文件与批量设备操作

“共享文件”已支持浏览目录、上传、下载、新建文件夹、重命名，以及删除文件或空文件夹。默认目录为 `R-Link-Server/shared/`，可在启动服务前用 `R_LINK_STORAGE_DIR` 指定其他绝对路径。只开放该共享区，单文件最多 64 MiB，不覆盖同名文件，不支持符号链接、目录联接或硬链接。下载保存到浏览器或桌面 WebView 的下载位置；Windows 实测保存到用户“下载”目录。

设备列表支持名称/地址/用户名搜索和检测状态筛选，“检测筛选结果”最多并发检查 4 台设备，可停止后续检测。清单可导入和导出为 JSON，仅包含地址与用户名，不包含密码、私钥或检测历史。导入会跳过已有主机与端口；无效条目或容量超限会撤销整次导入。操作说明与验证见[共享文件和设备批量管理](docs/shared-files-device-tools-20260919.md)。

## 验证和构建

```sh
npm test
npm run test:server
npm run verify:migration
npm run build
npm run tauri:dev
npm run tauri:build
```

[审查与验证结果](docs/audit-20260919.md)。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `apps/r-link-web/` | Web 客户端与 Tauri 桌面工程 |
| `R-Link-Server/` | API、认证、SSH、插件管理 |
| `demos/` | 网络、存储、串流、隧道演示 |
| `docs/` | 开发文档、审查结果与迁移记录 |
| `scripts/` | 本地启动与迁移完整性验证 |

FRP、域名/HTTPS、后台下载和 NetBird 组网管理已接入真实服务端：支持 TCP/UDP 隧道启停、Cloudflare DNS 管理、Caddy 自动 HTTPS、持久化下载队列，以及 NetBird 节点、分组、入网密钥、访问策略、网络资源与路由管理。组网需要另行部署 NetBird 控制面并在设备上安装 Agent。工具安装、环境变量、API、Docker/systemd 部署与功能边界见[服务端实现与部署](docs/server-implementation-20260922.md)。这是单机单管理员模式，没有多用户或角色体系；同一数据目录只运行一个服务进程。

尚未提供远程设备 SFTP/WebDAV 或点对点文件传输。R-Link 不内置 WireGuard、信令或中继服务；跨 NAT 组网由接入的 NetBird 提供，其控制面和 Agent 不作为 Git 子模块附带，按官方文档部署。Sunshine、Moonlight、RustDesk、FRP、Rclone 等第三方程序也需按各自文档安装并遵循许可证。
