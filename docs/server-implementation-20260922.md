# 服务端实现与部署

## 当前范围

原项目已有 FastAPI 服务端，设备清单、TCP 检测、SSH、插件及共享文件均有真实实现。此次补齐了 FRP、域名/HTTPS、后台下载和 NetBird 虚拟组网管理模块及对应 React/Tauri 页面，沿用单管理员服务密钥模式。

| 模块 | 已实现 |
| --- | --- |
| 设备与 SSH | 保留设备增删改查、导入导出、批量检测、SSH WebSocket |
| 插件与控制台 | 保留插件安装、配置、日志、进程管理与 ttyd 接入 |
| 共享文件 | 保留服务端共享区浏览、上传、下载和文件操作 |
| FRP | TCP/UDP 隧道配置、冲突检查、启停、日志、重启自启；真实调用 frpc |
| 下载 | HTTP/HTTPS 队列、3 路并发、暂停/继续/取消/删除、本机保存、重启恢复 |
| 域名 | HTTP 上游绑定、启用/禁用、DNS 解析和外部 HTTPS 证书检测 |
| DNS | Cloudflare A/AAAA/CNAME 查询、新建、删除；删除前核对域名归属 |
| HTTPS | Caddy 配置校验、应用、停止、日志及自动证书管理，恢复上次已应用配置 |
| 虚拟组网 | 通过 NetBird 管理 API 读取真实节点状态，管理分组、入网密钥、访问策略、网络资源与路由节点 |
| 运维 | SQLite 状态、单进程所有权锁、进程崩溃恢复、日志轮转、操作记录、Docker/systemd 示例 |

这是一套**单机、单管理员管理后端**。虚拟组网的数据面和控制面由独立的 NetBird 部署提供；R-Link 自身不运行 WireGuard、信令、中继或设备 Agent。还不包含多租户账号、角色体系、远端 SFTP/WebDAV、远程桌面串流、BT 下载或自动执行下载文件。FRP 需要可连接的 frps；DNS/公网证书仍需真实域名与网络条件。

## 结构与状态

FastAPI 生命周期创建 `Services`，持有下载、隧道和域名管理器。保留已有 API 与设备数据库，无需迁移旧设备。新模块的数据存于 `R_LINK_DATA_DIR/services.sqlite3`，默认 `R-Link-Server/data/`。数据库版本为 1，拒绝使用比当前程序更新的数据库版本。

- `downloads/`：未完成文件 `.part`、完成文件 `.file`；以 UUID 命名，原文件名仅用于下载响应。
- `processes/`：frpc/Caddy 配置与每进程最多 3 × 1 MiB 的轮转日志；日志 API 最多返回尾部 32 KiB。
- `certificates/`：Caddy 证书、私钥及 ACME 状态，必须持久保存。
- 操作记录：新模块最多保留 5000 条，API 返回最近 200 条，不记录令牌和下载 URL。单管理员模式不区分个人身份。

同一数据目录只允许一个服务端进程，**不要配置多个 Uvicorn workers**。程序启动时根据持久记录核对 PID、创建时间、可执行文件和工作目录，清理上次异常退出残留的自有进程，不按端口或进程名杀进程。正常退出先停止任务和子进程，再释放锁。

下载未完成任务会在重启后恢复；主动暂停、失败和取消的任务不会自行恢复。续传使用 `Range` 和强 ETag/Last-Modified，文件变化时重新下载或明确失败，避免拼接不同文件。没有验证标识时从头下载。单文件默认最大 512 MiB，最多保留 256 个任务；删除任务同时删除文件。文件大小限制可调整，但客户端“保存到本机”目前会缓冲 Blob，较大文件建议直接从服务端数据目录获取。

下载仅接受无用户名/密码的 HTTP/HTTPS URL，不执行文件。连接使用实际解析结果验证地址，默认拒绝私网、回环、链路本地和元数据地址；每次重定向重新验证，禁止 HTTPS 降级。受信内网下载必须在 `R_LINK_DOWNLOAD_ALLOWED_HOSTS` 显式列出精确主机名/IP。下载 URL 可能包含签名参数，因此数据目录也应视为敏感数据。

## 本机启动（Windows / Linux）

使用根目录现有 Python 环境和 Web 开发方式：

```powershell
.\.venv\Scripts\python.exe -m pip install -r R-Link-Server/requirements-test.txt
.\.venv\Scripts\python.exe scripts/install-service-tools.py
.\.venv\Scripts\python.exe R-Link-Server/main.py
# 另一个终端：npm run dev
```

安装脚本从官方 GitHub release 获取固定版本 frp **0.71.0** 与 Caddy **2.11.4**，校验 release API 发布的 SHA-256 后，只提取指定可执行文件到仓库 `binaries/`，不会修改系统 PATH 或安装系统服务。已存在不同内容的程序不会被覆盖。Linux 使用 `python` 替换 Windows 虚拟环境路径；脚本支持 amd64/arm64，macOS 应自行安装工具并配置绝对路径。

程序查找顺序：显式环境变量 → 系统 PATH → 仓库 `binaries/`。缺少 frpc/Caddy 时，其他模块仍可工作，界面显示具体缺项。

```powershell
# 在启动服务端的终端设置；填写你自己的值
$env:R_LINK_FRP_TOKEN = '<frps 的共享令牌>'
$env:R_LINK_CLOUDFLARE_TOKEN = '<仅授权目标区域 DNS 编辑的令牌>'
# 需要远程访问时，客户端“系统设置 → 服务访问”填写同一访问密钥
$env:R_LINK_API_TOKEN = '<随机的服务访问密钥>'
$env:R_LINK_HOST = '0.0.0.0'
.\.venv\Scripts\python.exe R-Link-Server/main.py
```

环境变量不会从 `.env` 自动加载，Shell/systemd 应显式设置；Docker Compose 会读取 `deploy/.env`。不要把真实密钥写入仓库。

| 变量 | 默认 / 用途 |
| --- | --- |
| `R_LINK_DATA_DIR` | `R-Link-Server/data`，新模块状态和数据 |
| `R_LINK_API_TOKEN` | 本地直连可省略；绑定非回环地址必须设置 |
| `R_LINK_HOST` | `127.0.0.1`；端口仍为 8210 |
| `R_LINK_CORS_ORIGINS` | 保留原有 Web/Tauri 来源，远程部署设置实际来源 |
| `R_LINK_FRPC_BINARY` | frpc 绝对路径，可选 |
| `R_LINK_FRP_TOKEN` | 默认 FRP 令牌变量；每个隧道可引用 `R_LINK_FRP_TOKEN_<名称>` |
| `R_LINK_CADDY_BINARY` | Caddy 绝对路径，可选 |
| `R_LINK_CLOUDFLARE_TOKEN` | Cloudflare DNS API 令牌，可选 |
| `R_LINK_NETBIRD_URL` | NetBird 管理服务 HTTPS 根地址，如 `https://netbird.example.com`；仅本机回环可使用 HTTP |
| `R_LINK_NETBIRD_TOKEN` | NetBird 服务用户的 Personal Access Token；仅服务端保存 |
| `R_LINK_ACME_STAGING` | `false`；开发时可用 `true` 请求不受浏览器信任的测试证书 |
| `R_LINK_DOWNLOAD_MAX_BYTES` | 536870912，单个下载的字节数上限 |
| `R_LINK_DOWNLOAD_ALLOWED_HOSTS` | 空；允许访问的内网下载主机，逗号分隔，无通配符 |

FRP 支持 TCP/UDP，每隧道最多一个映射，共 64 个；使用 TLS 传输及 token 认证。frpc 按目标地址直连，不继承 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY。令牌仅写入私有运行配置，停止时移除，返回前端的是环境变量名。Unix 使用私有目录和文件权限；Windows 部署时应通过 NTFS ACL 限制数据目录仅服务账号访问。**进程运行不等于隧道已经连通**，请查看日志并从预期入口测试端口。

域名最多 100 个，暂不支持通配符和 HTTPS 上游。DNS 可以手动维护；可选 Cloudflare 操作仅影响该绑定域名，创建的记录使用 DNS-only。修改绑定不会立即修改运行中的 Caddy；“应用 HTTPS”会校验配置，然后短暂重启此实例，启动失败尝试恢复此前运行配置。停止 HTTPS 会禁用重启恢复；绑定删除不会删除 DNS 记录。

公网证书需要域名指向此服务器，80/443 可达且无其他进程占用端口。应用时由 Caddy 自动完成 ACME 申请及续期；显示“进程运行”并不表示证书已签发。界面的检测从服务端检查域名当前对外提供的证书，CDN 情况下可能是 CDN 证书。此实现不读取或导出私钥到前端。

## 虚拟组网：部署和使用

1. 按 [NetBird 官方自建指南](https://docs.netbird.io/selfhosted/selfhosted-quickstart) 在可公网访问的 Linux 主机上部署 NetBird。使用它生成的部署配置；R-Link 的 `deploy/compose.yaml` 不包含 NetBird 服务。按官方要求配置域名、HTTPS 和 TCP 80/443、UDP 3478 的网络入口。
2. 在 NetBird 创建有相应管理权限的**服务用户 PAT**，参照 [Public API 认证说明](https://docs.netbird.io/manage/public-api)。将控制面地址及 PAT 分别设为 `R_LINK_NETBIRD_URL`、`R_LINK_NETBIRD_TOKEN`，然后重启 R-Link 服务端。Docker 部署填写 `deploy/.env`；容器中的 `localhost` 只指 R-Link 容器自身。
3. 在 R-Link 的“虚拟组网”页创建分组和入网密钥。在每台目标机器安装 NetBird Agent，并按界面给出的 `netbird up --management-url ... --setup-key ...` 命令入网。密钥完整值仅在创建响应中显示一次，R-Link 不持久化；后台列表会移除密钥值。
4. 在同一页面核对 NetBird 返回的节点地址、连接状态、分组与策略。可按需要创建网络、可访问资源和路由节点。路由节点还需按 NetBird 文档具备到目标网段的连接和转发能力。

R-Link 显示的“在线”是 NetBird 管理端报告的节点连接状态，不能证明两节点已建立直接 P2P 通道或目标网段可达；实际连通性请从已入网设备测试。NetBird 初始 Default 策略可能允许所有节点互访，新增一条允许策略不会自动收紧它。R-Link 的简化表单只编辑自己创建的单规则策略，避免覆盖其他复杂规则；在 NetBird 控制台管理复杂策略。未配置 PAT 时页面明确显示未配置，不生成虚拟节点或成功状态。管理 API 访问令牌只在服务端环境中使用，请勿放进前端环境变量或仓库。

## Docker Compose

仓库附带 Python 服务端与 Nginx 静态前端，API 和 SSH WebSocket 均通过 Nginx 转发。

```sh
# Linux 容器需要 Linux 工具，即使在 Windows 上运行 Docker Desktop
python scripts/install-service-tools.py --platform linux_amd64
cp deploy/.env.example deploy/.env
# 编辑 deploy/.env，替换访问密钥；可用 python -c "import secrets; print(secrets.token_urlsafe(48))" 生成
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build
```

访问 `http://127.0.0.1:8080`，在设置里填写访问密钥。服务端使用 UID 10001，数据保存在命名卷，默认不公开管理端口。若需要管理公网 HTTPS 域名：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.https.yaml up -d --build
```

此附加配置公开 80/443，只用于明确配置的域名。将域名上游设为 `web:80` 可发布管理界面；保留服务密钥认证。容器中的 `127.0.0.1` 指容器自身，访问其他容器使用其服务名，访问宿主机需使用平台支持的宿主机地址。生产远程访问使用 HTTPS。

本环境没有 Docker CLI，因此已提供配置但未执行容器构建或 Linux 部署；Windows 原生进程和 Web 构建已经验证。

## Linux systemd

示例为 `deploy/r-link.service`。将仓库放到 `/opt/r-link`，创建独立 `rlink` 系统用户和虚拟环境，在 `/etc/r-link.env` 设置环境变量（权限 0600）；为服务账号准备可写的配置、插件、日志、共享区及数据目录。模板允许绑定 80/443，以运行 Caddy。按实际安装路径调整后由运维安装并启用该单元，仓库不会自动修改系统服务。

## 接口

新接口与旧接口一致，使用 `Authorization: Bearer <服务密钥>`；没有密钥时只允许可信本地直连。完整类型与参数见 `/docs`、`/openapi.json`，前端契约在 `apps/r-link-web/src/api/services.ts`。

| 接口 | 方法 / 行为 |
| --- | --- |
| `/api/services` | GET，就绪状态与外部程序可用性 |
| `/api/audit` | GET，新模块最近操作记录 |
| `/api/downloads` | GET 列表、POST 新建 |
| `/api/downloads/{id}/{pause,resume,cancel}` | POST 控制 |
| `/api/downloads/{id}/file` | GET 已完成文件，支持框架的 Range 响应 |
| `/api/downloads/{id}` | DELETE 记录和文件 |
| `/api/tunnels` | GET 列表、POST 新建 |
| `/api/tunnels/{id}` | PUT 修改、DELETE 停止并删除 |
| `/api/tunnels/{id}/{start,stop}` | POST 启停 |
| `/api/tunnels/{id}/logs` | GET 日志 |
| `/api/domains` | GET 列表、POST 新建 |
| `/api/domains/{id}` | PUT 修改、DELETE 绑定 |
| `/api/domains/service` | GET HTTPS 进程及待应用状态 |
| `/api/domains/service/{apply,stop}` | POST 应用/停止 |
| `/api/domains/service/logs` | GET HTTPS 日志 |
| `/api/domains/{id}/check` | POST 解析和 TLS 检测 |
| `/api/domains/{id}/dns` | GET 查询、POST 创建 Cloudflare 记录 |
| `/api/domains/{id}/dns/{record_id}` | DELETE 属于该域名的记录 |
| `/api/mesh/status`、`/api/mesh/peers` | GET 真实组网状态/节点列表；节点可 PUT 重命名、DELETE 移除 |
| `/api/mesh/groups`、`/api/mesh/setup-keys` | 分组增删改查；入网密钥创建、列表、撤销、删除 |
| `/api/mesh/policies` | 策略列表、新建、编辑 R-Link 单规则策略、删除 |
| `/api/mesh/networks` | 网络增删改查；`/{id}/resources` 和 `/{id}/routers` 管理可访问资源与路由节点 |

关键错误：401 未授权，404 不存在，409 状态或资源冲突，422 参数/配置错误，502 上游错误，503 外部程序或凭据未配置。下载异步错误写入任务状态。新接口拒绝额外字段和无效主机/端口，前端不会显示虚构成功状态。

## 验证和备份

```powershell
.\.venv\Scripts\python.exe -m pytest R-Link-Server -q
$env:R_LINK_RUN_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest R-Link-Server/test_services_integration.py -q
# 前端：npm test；npm run build
```

测试覆盖认证、持久化、单 worker 锁、下载真实 HTTP 传输、暂停续传、重启恢复、ETag 变化、Range 回退、大小上限、重定向到内网拦截、硬链接防护、进程清理/日志脱敏、PID 复用保护及 DNS 域名归属。可选集成测试使用官方 frpc/frps 真正转发 TCP 字节，并用 Caddy 校验、运行代理与恢复。集成测试只绑定回环高位端口，不修改公网 DNS，不申请证书、不安装系统信任根。

当前环境没有用户的 Cloudflare 凭据和可用公网域名，真实 DNS 修改及 ACME 签发未做现场验证；单元测试覆盖请求参数、域名限制和失败行为。

2026-09-23 本机验收结果：服务端 **181 项通过、2 项默认跳过**；另行启用真实 frp/Caddy 集成后，这 **2 项通过**。前端 **48 项通过**，桌面窗口行为 **12 项通过**，TypeScript 检查、Vite 生产构建和 Compose YAML 解析通过。NetBird 集成的 MockTransport 测试覆盖 API 请求契约、令牌边界及错误处理；此环境没有 NetBird 控制面及 Agent，尚未完成公网跨 NAT 端到端连通性验收。

`verify_web_migration.py` 未通过：其首个失败项是本轮开始前已有改动的 `apps/r-link-web/src/api/types.ts`，当前 `PluginLogsResponse.logs` 类型与迁移时保存的哈希不同。本轮未修改该文件或归档清单，未通过重写哈希掩盖这项既有差异。

备份时先停止服务端，再复制 `R_LINK_DATA_DIR`、原设备数据库、共享区、插件与配置目录；密钥环境变量另行安全备份。停止服务确保 SQLite WAL 和下载文件处于一致状态。还原到相同版本或兼容升级版本，确认目录权限和外部工具路径后启动。保留 Caddy 证书状态避免重复签发。不要只复制正在运行的 `.sqlite3` 主文件。

实现依据：[FRP 配置](https://gofrp.org/en/docs/reference/client-configures/)、[Caddy 自动 HTTPS](https://caddyserver.com/docs/automatic-https)、[Caddy 命令行](https://caddyserver.com/docs/command-line)、[Cloudflare DNS API](https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/create/)、[NetBird Public API](https://docs.netbird.io/api)。
