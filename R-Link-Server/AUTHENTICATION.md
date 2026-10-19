# R-Link 多用户认证

R-Link 使用独立的 OIDC confidential client 直接向可信 Keycloak issuer 登录。
R-Auth 作为账户中心可共用该 issuer 和同一用户主体，但 R-Auth Cookie、邮箱、userId 和第三方应用 token 都不是 R-Link 凭据。
用户主键仅为精确的 `(issuer, subject)`，相同邮箱不会自动合并。设备和业务库目前共享，访问由角色限制。

## 配置

安装 `requirements.txt`（锁定 `Authlib==1.8.0`），设置：

```dotenv
R_LINK_AUTH_MODE=oidc
R_LINK_PUBLIC_URL=https://175.178.16.90/r-link
R_LINK_OIDC_ISSUER=https://175.178.16.90/auth/realms/rlink
R_LINK_OIDC_CLIENT_ID=rlink
R_LINK_OIDC_CLIENT_SECRET=<confidential-client-secret>
R_LINK_BOOTSTRAP_ADMIN_SUBJECT=<exact-keycloak-subject>
```

issuer 必须与 discovery 的 `issuer` 精确一致；所有 IdP 端点要求 HTTPS 且与 issuer 同源，禁止重定向和环境代理。
在 Keycloak 只登记精确回调 `https://175.178.16.90/r-link/api/auth/callback`，开启 standard authorization-code flow 和 S256 PKCE，关闭 implicit flow 和 direct access/password grant。
反向代理把 `/r-link/api/` 去前缀后传给后端；公开地址和 Cookie Path 使用 `/r-link`，不依赖不可信 Forwarded 头来生成回调。
HTTPS Cookie 为 HttpOnly、Secure、SameSite=Lax、无 Domain；同域其他路径上的应用仍须可信，因为 Cookie Path 不能隔离恶意同源应用。
`R_LINK_CORS_ORIGINS` 仅登记可信前端和 Tauri origin，不能用 `*`。

认证数据库默认 `config/auth.sqlite3`，可用 `R_LINK_AUTH_DB` 指定持久卷；它保存用户、会话哈希和短期登录事务。
state、浏览器 binding 和桌面 poll_secret 仅保存哈希，nonce/PKCE verifier 加密，默认密钥由 confidential client secret 派生，也可设置独立高熵 `R_LINK_AUTH_FLOW_SECRET`。
IdP access、refresh、ID token 不持久化，不传给前端。登录事务五分钟过期、单次消费；会话默认八小时，支持 `R_LINK_SESSION_SECONDS`（300–28800 秒），不自动无限续期。
多 worker 必须使用相同配置、同一 SQLite 文件；不要分别存储不共享的认证数据库。

## 角色和注销

新用户默认 `pending`，需要管理员批准；只有预先配置的精确 bootstrap subject 首次创建时成为 `admin`，不存在“第一个登录者成为管理员”。
`viewer` 只允许设备列表/详情、NetBird status/peers/groups、系统 info/resources/uptime/network。
`operator` 允许日常设备管理、自己的 SSH、共享文件和传输业务。服务器插件和配置/日志、console、审计、隧道和域名/DNS/HTTPS、NetBird setup-key 和组网权限写入（含设备 link/revoke）、用户管理要求 `admin`。
多用户模式禁止启动或返回裸 ttyd 控制台；使用具有会话授权的 SSH。部署者须移除历史已发布的 `/console` 裸代理，并停止已有外部 ttyd 进程；本应用不会终止不属于本应用的进程。
GET `/api/plugins/status/all` 仅返回运行状态，operator 可读取；其它插件端点均要求 admin。

管理员 PATCH 角色/禁用会增加用户版本并撤销全部会话和 SSH 连接，用户须重新登录。
浏览器登录轮换会话，同一浏览器已有旧注销请求会撤销轮换后的会话族；logout 也取消关联的在途登录事务。
携带已退役 Cookie 的旧标签页不能创建新登录族，收到 409 后需回到首页重新开始登录。首次登录尚无 Cookie 的两个标签页应避免同时发起登录；每个回调仍须匹配当前浏览器的单次 binding。
WebSocket 使用一次性、60 秒、scope=ssh 的票据，并持续重新检查会话、角色和禁用状态。服务密钥轮换也让该主体票据失效。
`R_LINK_API_TOKEN` 可作为受控自动化 admin 凭据；当请求包含用户 Cookie 时，优先处理用户，过期/禁用不会退回服务密钥权限。

## 前端契约

- GET `/api/auth/config`: `{mode, login_enabled, desktop_login_enabled}`。
- GET `/api/auth/session`: `{mode, authenticated, user, csrf_token, session_context, expires_at}`，匿名返回 200。
- GET `/api/auth/login`: 固定回调和固定公开首页，不能指定任意回跳地址。
- POST `/api/auth/logout`: 撤销当前用户会话族，返回 204。
- GET `/api/auth/users`: admin，返回 `{users}`。
- PATCH `/api/auth/users/{id}`: admin，body `{role?, disabled?}`，返回更新的用户；最后一个活跃管理员不能被禁用/降级。
- POST `/api/auth/ws-token`: operator/admin，返回 `{token, scope:'ssh', expires_in:60}`。

Cookie 写请求必须同时携带精确公开 Origin、`X-R-Link-CSRF` 和 `X-R-Link-Session-Context`。
桌面 bearer 写请求也必须携带匹配的 `X-R-Link-Session-Context`。上下文不一致返回 409 `SESSION_CHANGED`；旧动作不能自动重试。
所有认证响应均 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`。

Tauri 调 POST `/api/auth/desktop/start`，获得 `{login_url, flow_id, poll_secret, expires_in:300}`，只在系统浏览器打开服务端返回的同源 `/api/auth/desktop/login?flow_id=...`。
客户端以 body POST `/api/auth/desktop/exchange` `{flow_id,poll_secret}`，未完成为 202 `{pending:true}`，成功一次返回 `{token,user,expires_at}`。
poll_secret 永不出现在 URL；桌面 token 是独立、有限期的 R-Link opaque session，只保存在内存，用 Bearer 发给配置的可信 R-Link 服务。
随后 GET session 获取 session_context。更换服务器、注销、关闭客户端或收到 401 时清除它。没有任意 return origin 或跨应用 token 转交。

参考：
[Authlib Starlette OIDC](https://docs.authlib.org/en/stable/client/starlette.html)、
[Authlib HTTP client PKCE](https://docs.authlib.org/en/stable/oauth2/client/http/index.html)。
