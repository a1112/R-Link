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

复制 `apps/r-link-web/.env.example` 为 `.env.local`，填写公开的 Supabase URL/key。在服务端进程环境设置同一项目的 `SUPABASE_URL`、`SUPABASE_ANON_KEY`，并用 `R_LINK_ADMIN_USER_IDS` 指定管理员用户 UUID（多个用逗号分隔），或在 Supabase 的管理员管理字段 `app_metadata.role` 中赋值 `admin`。普通账号不能管理插件或本机控制台。

```sh
# 已激活 Python 环境的终端
npm run dev:server
# 另一个终端
npm run dev
```

Web 地址为 `http://127.0.0.1:4322`，API 地址为 `http://127.0.0.1:8210`，API 文档在 `/docs`。Web 开发代理已连接 API；静态部署需配置反向代理或 `VITE_API_BASE_URL`。服务端 CORS 可通过 `R_LINK_CORS_ORIGINS` 设置允许的来源（逗号分隔）。`DEV=true` 启用服务端热重载。

SSH 使用服务端用户的 `~/.ssh/known_hosts` 校验主机密钥，也可通过 `R_LINK_SSH_KNOWN_HOSTS` 指定可信文件；连接必须提供目标主机的密码或私钥。多进程部署须设置相同的私有 `R_LINK_WS_TOKEN_SECRET`。

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
