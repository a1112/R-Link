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

设备列表支持添加、编辑、删除和持久保存地址，按需从服务端检测指定 TCP 端口，并可将地址带入 SSH 连接表单。默认数据库为 `R-Link-Server/config/devices.sqlite3`，可用 `R_LINK_DEVICES_DB` 指定位置；不保存设备密码或私钥。检测结果带时间，不代表整台设备健康。仪表盘按网卡显示真实流量采样，不再展示虚构的隧道数量。

桌面版提供系统托盘：单击恢复窗口，右键打开设备管理、SSH、设置、隐藏窗口或退出。默认关闭窗口后驻留；在“系统设置 → 通用设置”或托盘菜单切换，设置在系统应用配置目录的 `desktop.json` 中保存。重复启动会恢复已有窗口。切换管理页和隐藏窗口会保留当前 SSH 会话；退出客户端会断开客户端连接，不停止独立服务端和插件。

[设备网络与托盘审查记录](docs/network-tray-audit-20260919.md)。

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
| `scripts/` | 迁移完整性验证 |

部分页面仍使用演示数据，不能视为完整的 FRP、远程桌面或组网产品。Sunshine、Moonlight、NetBird、RustDesk、FRP、Rclone 等第三方项目不再作为 Git 子模块附带；部署时按各自文档安装并遵循其许可证。
