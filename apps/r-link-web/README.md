# R-Link Web 客户端

从 `lcxinc/R-Link-Web` 迁入的 React 管理界面，与本仓库 `R-Link-Server` 配套。保留原有页面和 Tauri 工程；管理界面在有效 Supabase 会话出现后才挂载。

## 本地开发

```sh
cd apps/r-link-web
npm ci --ignore-scripts
# 复制 .env.example 为 .env.local，并填写自己的配置
npm run dev
# http://127.0.0.1:4322
```

设置 `VITE_SUPABASE_URL` 和 `VITE_SUPABASE_ANON_KEY`，使用与服务端相同的 Supabase 项目。只在浏览器配置公开的 anon/publishable key，不能配置 service-role key。缺少配置时显示设置提示。登录、注册及 OAuth 是否可用取决于该项目的账号和回调配置。

开发模式默认通过 Vite 将 `/api`（含 WebSocket）和 `/health` 转发到 `http://127.0.0.1:8210`。部署时将这些路径反向代理到服务端，或者构建前填写 `VITE_API_BASE_URL` 并配置服务端 CORS；HTTPS 页面应使用 HTTPS/WSS 服务地址。Vite 的代理不会随静态构建发布。原有 `/config` 声明没有对应的服务端根路由，不能视为可用接口。

服务端可设置仅服务端持有的 `R_LINK_WS_TOKEN_SECRET`；未设置时生成进程随机密钥。多进程部署必须设置相同的随机密钥，否则票据不能跨进程验证。不能使用公开 anon key 作为签名密钥。

服务端另开终端：

```sh
cd R-Link-Server
python -m venv .venv
# 激活虚拟环境后执行
python -m pip install -r requirements.txt
# 在进程环境中设置 SUPABASE_URL、SUPABASE_ANON_KEY
python main.py
```

HTTP 管理请求按次读取当前会话，携带 Bearer token，仅发送到已配置的 API origin。SSH 先通过 `/api/auth/ws-token` 获取短期票据，再使用 WebSocket subprotocol 认证；不把登录 token 放在 URL 中。取消连接会取消正在获取的票据，并关闭已创建的套接字。

## 验证

```sh
# apps/r-link-web
npm test
npm run build
# R-Link-Server
python -m pip install -r requirements-test.txt
python -m pytest test_auth_and_plugin_security.py test_web_client_contract.py -q
```

当前审查结果见 [2026-09-19 审查记录](../../docs/audit-20260919.md)。构建包含严格 TypeScript 检查；浏览器代码不包含独立部署的 `src/supabase/functions` Deno 服务。

已补齐桌面图标并修正 Tauri 配置。原生签名安装包与真实 Supabase/SSH 联调另行验证。部分功能页仍包含演示数据。

插件和本机控制台管理需要管理员权限；配置方法以及 SSH 主机密钥校验见[根目录说明](../../README.md)。插件 ZIP 的名称来自清单，已安装插件须先卸载再替换。

[迁移清单与原始文件](../../docs/repository-consolidation/R-Link-Web/README.md)。旧 `.env` 未自动启用，编辑器文件仅作归档；历史文档和归档代码仅供追溯，当前配置以本文为准。
