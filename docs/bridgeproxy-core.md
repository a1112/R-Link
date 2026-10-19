# R-Link 的 BridgeProxy Core 接入

R-Link 可管理独立运行的 BridgeProxy Core。本机桌面目标和服务端目标分别选择，
不会把部署在 NAS/Linux 的服务端回环地址当成用户 Windows 电脑。未配置时返回
不可用，R-Link 不会启动 Core、安装网卡、修改代理或伪造运行状态。

## 本机桌面目标

在 R-Link 的“网络出口与代理”选择“这台电脑的 Core”。如果独立 BridgeProxy
客户端已经运行并启用控制 API，直接填写它的 `BridgeProxy-data` 绝对目录；
同一个数据目录由其现有 Core 实例持有，不需要另开 daemon。

也可以从独立 Core 便携包启动专用实例：

```powershell
.\bridgeproxy-core.exe --idle --data-dir C:\BridgeProxyCore\R-Link-data --control-port 0
```

`--idle` 只启动核心管理宿主，不启动代理流量接管；服务启停由后续明确操作决定。
端口 0 选择可用控制端口，R-Link 从受保护的元数据读取真实端口，无需在界面输入。
在 R-Link 填写 `C:\BridgeProxyCore\R-Link-data`，按需勾选本机控制授权并连接。
数据目录和凭据应由同一 Windows 用户创建；只读连接不提供验证码或写操作。

本机凭据通过原生 `r-link-core` 适配器读取 DPAPI，不显示到页面。授权保留在当前
R-Link 进程内，账号切换会撤销。断开管理连接或关闭 R-Link 不会停止独立 Core。
TUN 要求 Core 具有管理员权限；本机提权、安装和双端验证码核对仍须明确确认。

Core 包及 BridgeProxy GUI 包分别构建和打包，默认版本均为本轮源码中的 0.6.1；
实际发布前应按各产品版本策略发布。此接入需要包含 capabilities/snapshot 等新增
接口的构建，旧版同名版本缺少接口时会如实返回不可用。

## 服务端目标

管理员在启动 R-Link 服务端前配置以下环境变量：

| 变量 | 含义 |
| --- | --- |
| `R_LINK_BRIDGEPROXY_URL` | 服务端本机 Core 的控制 API，例如 `http://127.0.0.1:17893`；默认不配置 |
| `R_LINK_BRIDGEPROXY_READ_TOKEN` | Core 的 64 位十六进制 read 凭据，用于普通读取 |
| `R_LINK_BRIDGEPROXY_CONTROL_TOKEN` | 可选的独立 control 凭据；未配置时不提供控制及 SAS 读取 |

URL 只接受 HTTP 回环端点与显式端口，不接受路径、用户信息、查询或远端主机。
`localhost` 规范化为 `127.0.0.1`，无需 DNS 解析。凭据由管理员通过 Core 自身的
安全机制取得，保存在服务进程环境与内存中，不经前端输入或输出。修改后重启
R-Link 服务端；轮换 Core 凭据后也须更新该配置。不要将实际凭据写进仓库或日志。

Docker 中的 `127.0.0.1` 指容器本身，不是宿主机或桌面电脑。普通 NAS 部署保持
不配置，不能改为宿主机网关来绕过本机接口边界。两个服务端镜像均从仓库根构建，
将共享路由合同复制到 `/contracts/bridgeproxy-v1.json`；直接构建使用
`docker build -f R-Link-Server/Dockerfile .`，不能再以服务端子目录作为构建上下文。
NAS 源码发布包显式包含该合同，缺失时打包失败。

持有 R-Link 管理员权限并不自动拥有其他电脑的 Core。配置以上变量是在明确授予
R-Link 管理这个服务端本机实例的权限。Core 的系统代理和应用代理操作作用于运行
Core 的 Windows 用户；TUN、配对及安装仍遵循 Core 自身的权限和本机确认要求。

## API 合同

`/api/bridgeproxy/v1` 保留 Core `/v1` 的业务后缀和 HTTP 方法，例如
`GET /api/bridgeproxy/v1/status`、`PATCH /api/bridgeproxy/v1/config`。
R-Link 只接受共享合同白名单中的业务路由，不提供任意 URL 或命令转发。

- `GET /adapter` 描述适配器配置，`target=server`、`endpoint_scope=server-loopback`。
  `configured=true` 仅代表配置完整，`state=unobserved` 不能解释为 Core 正在运行。
- 普通读取要求 R-Link viewer 或更高角色，始终使用 Core read 凭据。
- 写操作要求 R-Link admin，使用 Core control 凭据。
- `GET /pairings/control` 是唯一 SAS 读取入口，要求 admin 并映射 Core 的
  `GET /v1/pairings` control 视图。普通 pairings、snapshot、operations 递归移除验证码。
- 保留 `{api_version: "v1", data|error}` 外壳、上游 HTTP 状态、ETag、请求的
  `If-Match` 和 `Idempotency-Key`；请求原始 JSON 字节保持不变。
- 写入受理仍为 HTTP 202，通过 operations 查询完成状态，再读取 runtime/status
  等确认实际结果。适配器不自动重试、不代替轮询，也不把 operation 成功当作链路可用。
- 未配置、连接失败返回 503，超时返回 504，非法/超大响应返回 502。
  超时、连接中断或响应错误不能证明写操作没有执行，应查询现有 operation 和实际状态；
  不要盲目重发。

请求不向 Core 发送浏览器 Cookie、Origin 或 R-Link 凭据。客户端禁用环境代理、
重定向及连接复用；最多 8 个并发请求，单请求总期限 10 秒，请求体上限 1 MiB，
响应上限 4 MiB。响应二次移除凭据、密码、私钥及 custom_json；自定义出站内容
仅可写入 Core，不会通过读取接口返回。

Core 接口详情与配置版本、幂等和异步操作语义以其 `docs/API.md` / OpenAPI 为准。
能力、聚合快照和操作列表通过 Core 的 `/v1/capabilities`、`/v1/snapshot`、
`/v1/operations` 读取；旧 Core 缺少接口时保持真实 404，不冒充支持。
