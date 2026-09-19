# R-Link Web 客户端

React/Tauri 管理界面，与本仓库 `R-Link-Server` 配套。启动后直接显示仪表盘，不需要云账号、登录注册或外部数据库。

## 本地开发

```sh
cd apps/r-link-web
npm ci --ignore-scripts
npm run dev
```

Web 地址为 `http://127.0.0.1:4322`。另开终端在 `R-Link-Server` 安装 `requirements.txt` 并执行 `python main.py`。服务端默认监听 `127.0.0.1:8210`，本机访问无需密钥。

开发模式通过 Vite 将 `/api`（含 WebSocket）和 `/health` 转发到服务端。静态部署应配置反向代理，或者在构建前通过 `.env.local` 设置 `VITE_API_BASE_URL`；Vite 开发代理不会随静态构建发布。HTTPS 页面应使用 HTTPS/WSS 服务地址。

## 服务访问

远程部署和反向代理访问必须在服务端设置 `R_LINK_API_TOKEN`；对外监听时另设 `R_LINK_HOST`。在“系统设置 → 服务访问”填写相同密钥。密钥按 API 来源保存在 `sessionStorage`，可随时清除；每次请求读取当前密钥，并拒绝向其他来源或重定向发送。清除或更新密钥会重新加载当前功能页。

跨域部署通过服务端 `R_LINK_CORS_ORIGINS` 指定允许的浏览器来源。设置访问密钥后，本机请求也需要携带它。此模式不提供云账号或多用户权限管理。

SSH 先申请 60 秒短期票据，再通过 WebSocket subprotocol 连接；服务密钥不写入 URL。多进程服务需要共享私有 `R_LINK_WS_TOKEN_SECRET`。目标 SSH 仍需密码或私钥，并使用可信 `known_hosts` 验证主机，详见[根目录说明](../../README.md)。

## 验证与构建

```sh
npm test
npm run build
npm run tauri -- build --debug --no-bundle
```

构建包含严格 TypeScript 检查。部分功能页仍包含演示数据。插件 ZIP 的名称来自清单，已安装插件须先卸载再替换。

[迁移清单与原始文件](../../docs/repository-consolidation/R-Link-Web/README.md)保留历史来源证据，归档中的旧配置与代码不参与运行。当前访问配置以本文为准。
