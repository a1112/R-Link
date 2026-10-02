# 云端部署与全部设备接入

本次代码将原设备清单与 NetBird 节点纳入统一管理：设备分类、平台、标签、备注、服务入口、网关关联、自动同步、明确的在线观测和入网撤销。R-Link 集中运行在云端；各设备安装适合其平台的 NetBird 客户端，管理界面可通过浏览器或 R-Link 桌面客户端使用。

## 1. 云端部署

先同步整个 Git 仓库，包括 deploy/nginx.conf。R-Link 的 Compose 不包含 NetBird 控制面；按 [NetBird 自建指南](https://docs.netbird.io/selfhosted/selfhosted-quickstart) 部署控制面，或使用现有 NetBird 服务。为该控制面创建有设备及组网管理权限的服务用户 PAT，见 [Public API 认证](https://docs.netbird.io/manage/public-api)。

在云端仓库根目录运行：

```sh
cp deploy/.env.example deploy/.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# 将生成的值填入 deploy/.env 的 R_LINK_API_TOKEN，再填写 NetBird 配置。
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build
docker compose --env-file deploy/.env -f deploy/compose.yaml logs --tail=100 server
```

deploy/.env 的关键设置：

```dotenv
R_LINK_API_TOKEN=<你生成的 R-Link 服务访问密钥>
R_LINK_NETBIRD_URL=https://netbird.example.com
R_LINK_NETBIRD_TOKEN=<NetBird 服务用户 PAT>
R_LINK_DEVICE_SYNC_INTERVAL=60
R_LINK_DEVICE_STALE_SECONDS=180
R_LINK_WEB_BIND=127.0.0.1
R_LINK_CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,tauri://localhost,http://tauri.localhost
```

R_LINK_NETBIRD_URL 填写 HTTPS 源地址，不带 /api、用户名或查询参数。PAT 留在云端环境配置中。R-Link 服务访问密钥用于管理界面，NetBird 入网密钥用于设备注册；它们分别使用。

默认 Web 入口监听云端本机 127.0.0.1:8080。通过现有 HTTPS 反向代理将 https://rlink.example.com 转发至该入口。如果宿主机使用 Caddy，可以在其配置加入：

```caddyfile
rlink.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

若反向代理本身运行在容器里，将上游改为该容器可访问的 R-Link Web 服务地址；容器内 127.0.0.1 指容器自身。API 与 SSH WebSocket 由仓库内 Nginx 配置统一转发。NetBird 与 R-Link 共用一台云服务器时，由同一 HTTPS 入口按域名分发，避免各自重复绑定 80/443。

使用 R-Link 管理的 Caddy 发布入口时，按[已有部署说明](server-implementation-20260922.md#docker-compose)安装 Linux 工具并使用 compose.https.yaml，将域名上游设为 web:80。设备同步本身不需要 frpc/Caddy 二进制。

## 2. 各设备安装

支持的 OS 版本、CPU 架构和安装包以各平台官方说明为准：

| 设备 | 官方安装入口 | 接入方式 |
| --- | --- | --- |
| Windows 电脑/服务器 | [Windows](https://docs.netbird.io/get-started/install/windows) | GUI 或 CLI |
| Linux 服务器/电脑 | [Linux](https://docs.netbird.io/get-started/install/linux) | CLI 或受支持的桌面环境 |
| macOS | [macOS](https://docs.netbird.io/get-started/install/macos) | GUI 或 CLI |
| Android 手机/平板 | [Android](https://docs.netbird.io/get-started/install/android) | NetBird Android App |
| iPhone/iPad | [iOS](https://docs.netbird.io/get-started/install/ios) | App Store 的 NetBird App |
| Synology/TrueNAS | [Synology](https://docs.netbird.io/get-started/install/synology)、[TrueNAS](https://docs.netbird.io/get-started/install/truenas) | 按相应 NAS 指南安装 |
| OpenWrt/MikroTik | [OpenWrt](https://docs.netbird.io/get-started/install/openwrt)、[MikroTik](https://docs.netbird.io/get-started/install/mikrotik) | 设备支持时直接安装，否则经网关 |
| 打印机、摄像头、其他 IoT | [网关网络](https://docs.netbird.io/manage/networks) | 通过可运行 NetBird 的网关访问 |

CLI 设备安装完成后，连接同一个控制面：

```sh
netbird up --management-url https://netbird.example.com
netbird status
```

按客户端提示完成登录。Linux 的系统服务操作可能需要 sudo。无人值守设备可在 R-Link 的“虚拟组网 → 入网密钥”创建单次密钥，按页面指引在目标设备使用；分组、时效和使用次数以实际配置为准。完整密钥仅在创建时显示。

Android 的自建服务入口位于 Change Server，可填写控制面地址并按需添加入网密钥；随后允许系统 VPN 连接。iOS 使用官方 App，按其当前界面配置同一控制面并完成登录。相关步骤见上表官方页面。

设备入网后，在 R-Link“设备管理”点击“同步组网设备”，或等待自动同步。R-Link 不会默认认定手机、NAS 或新节点提供 SSH；编辑设备选择真实的服务入口。

## 3. 连接云端管理界面

手机和电脑浏览器打开 https://rlink.example.com，在“系统设置 → 服务访问”填写 R_LINK_API_TOKEN。浏览器同源访问时服务地址可以留空。

安装好的 R-Link 桌面客户端同样在该设置填写 https://rlink.example.com 和访问密钥，保存连接后即可读取云端设备。服务地址保存在本机；密钥只保存在当前会话，按 API 源地址隔离。改变服务地址会关闭当前 SSH 会话并刷新数据，需要重新填写目标服务的密钥。

自建桌面客户端仍使用根目录的 npm run tauri:build；其构建依赖见根目录 README。手机使用网页管理界面与 NetBird App。

## 4. 网关后的设备

1. 在同一局域网选一台能访问目标设备的电脑、Linux 主机或受支持路由器，安装 NetBird 并入网。
2. 同步该节点，在 R-Link 设备清单中将其标记为路由器或服务器。
3. 在“虚拟组网 → 网络路由”创建网络、目标单机/网段资源和路由节点，并配置允许所需来源分组访问的策略。复杂资源策略可在 NetBird 控制台管理。
4. 在设备管理中登记 IoT 等设备的实际地址和 TCP 服务端口，选择该直接入网节点为网关，填写类型、标签和服务入口。
5. 从已经入网的设备实际访问目标服务，核对路由、策略和目标设备自身服务。网络转发条件见[官方网关说明](https://docs.netbird.io/manage/networks/how-routing-peers-work)。

清单的网关关联记录管理关系；实际网络权限由 NetBird Network/Resource/Router/Policy 决定。网关在线不会让其后的所有设备显示在线。R-Link 端口检测从云端服务发起；云端如果也需要直接检测覆盖网/局域网地址，必须具备相应 NetBird 路由。安装在宿主机的 VPN 接口不会自动赋予隔离容器同样的路由，请按部署网络配置连接。

## 5. 状态与设备生命周期

| 显示 | 含义 |
| --- | --- |
| 组网在线/离线 | 控制面最近一次成功观测的连接状态 |
| 组网未知 | 尚未关联、未配置、地址冲突、控制面失败、观测过期或控制面已切换 |
| 已从组网移除 | 成功同步的快照里不再包含原节点 |
| 已撤销入网 | 操作员明确撤销该节点，上游删除成功或确认节点已经不存在 |
| 端口可达/不可达 | 带时间的单个 TCP 端口检测，与组网状态分开 |

同步按控制面地址和 peer_id 保持身份，不会把 IP 相同的记录自动合并。地址冲突会在同步结果中报告；可明确关联已有清单到相应节点。若该节点已被其他清单绑定，先处理重复记录再关联。

删除清单会保留排除记录，防止下一次自动同步恢复它；设备仍保留 NetBird 网络身份。重新关联时，添加/选择手工清单，明确填写该 peer_id，服务端验证后解除排除。撤销入网会调用 NetBird 删除节点并保留撤销记录；需要再次接入时，按官方客户端流程重新注册。撤销失败会显示错误，不会显示成功。

设备类型和标签用于管理分类；访问策略继续在“虚拟组网”管理。服务入口可选 SSH、HTTP(S) 网页或无服务。网页入口能否在当前浏览器打开，取决于当前设备是否入网以及目标服务与策略配置。

## 6. 同步、数据迁移与备份

R_LINK_DEVICE_SYNC_INTERVAL 默认60秒，设为0关闭自动同步并保留手动同步。R_LINK_DEVICE_STALE_SECONDS 默认180秒，过期观测显示未知。修改环境变量后重启服务。每个数据目录只运行一个服务进程。

升级启动时自动迁移旧设备数据库，保留 UUID、地址、用户名和原 TCP 观测。新同步节点默认没有远控入口。设备容量仍为256台；同步容量不足会返回错误并撤销本次数据写入。

设备页面导出 v2 JSON，保留可移植的分类、平台、标签、备注和服务设置。API 默认导出 v1，兼容旧工具。v1/v2 都不含密码、私钥、PAT、入网密钥、检测历史、NetBird 身份和网关 UUID；在另一个服务导入清单后，需要同步/关联节点并重新选择网关。

完整备份时先停止服务，再备份设备数据库以及数据、共享文件、插件、配置和日志卷；NetBird 自身数据与环境密钥另行备份。数据库备份保留外部身份、排除记录及网关关联，详见[备份说明](server-implementation-20260922.md)。

## 7. 部署后验收

至少选两台处于不同网络的设备完成一次真实验证：入网后同步可见、断开后显示离线、编辑标签后同步仍保留、按策略访问真实服务、撤销后节点被移除。再用一台网关验证 IoT 服务访问。移动设备需要实际允许 VPN 连接并完成登录。

仓库自动测试覆盖数据库迁移、API 鉴权、受控 NetBird HTTP 请求、状态失效、同步竞争与界面交互；本机测试没有替代你的云端、跨 NAT、实体设备安装和网络验收。
