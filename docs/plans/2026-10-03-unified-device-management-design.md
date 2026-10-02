# 统一设备接入与管理设计

日期：2026-10-03。用户已确认代码实现，之后自行同步云端并在各设备安装客户端。

## 目标与边界

沿用 FastAPI、SQLite、React/Tauri 和 NetBird，为电脑、服务器、NAS、手机、路由器及网关后的 IoT 提供统一设备清单与接入管理。NetBird 提供设备端网络连接与在线观测。终端、网页服务按实际配置开放，端口可达与组网在线独立显示。不能安装客户端的设备经已有 NetBird Network/Resource/Router/Policy 接入；清单网关关联用于管理展示，不自行放行网络策略。

## 数据与兼容性

保留原设备 UUID、host/port/username、revision 和探测状态。迁移添加 device_type（computer/server/nas/mobile/router/iot/other）、platform（unknown/windows/linux/macos/android/ios/other）、tags（最多16个、每项32字符）、notes（500字符）、access_mode（ssh/web/none）、web_scheme（http/https）、gateway_id。旧输入仍可用，旧 PUT 省略新字段时保留已有元数据。

来源为 manual/netbird/gateway。NetBird 身份按管理服务源地址加 peer_id 识别，不按 IP 自动合并。同步创建的节点默认 access_mode=none，由操作员显式配置服务。gateway_id 仅关联未撤销的直接入网设备，禁止悬空、递归及自引用。保留256台容量；导入和同步事务不部分写入。

默认 v1 导出兼容旧客户端；v2 保留可移植的类型、平台、标签、备注及服务配置，不导出密钥、观测历史、外部身份或网关 UUID。完整身份与网关关联随数据库备份。

## 同步与生命周期

后台默认每60秒同步一次，R_LINK_DEVICE_SYNC_INTERVAL=0 可切换手动。校验完整快照后事务更新；保留本地标签、备注、用户名和服务配置。地址变动增加 revision 并清空旧探测。上游删除节点标记 removed，不删除清单。失败、过期或切换控制面时显示 unknown。默认180秒观测过期，通过 R_LINK_DEVICE_STALE_SECONDS 配置。

删除清单不撤销网络权限；持久排除记录防止同步复活。显式 link 将清单关联真实 peer；已被其他记录绑定则返回冲突，不能隐式合并。revoke 调用 NetBird 删除节点，成功后保留 revoked 记录；对已经验证属于当前管理服务的绑定节点，上游 404 视为节点已不存在的幂等成功，其余失败保留原记录并返回错误。操作纳入服务审计。网关在线不证明其后设备在线，网关状态单独显示。

## API 合同

- GET/POST /api/devices、PUT/DELETE /api/devices/{id} 保留合同，返回新增元数据。
- GET /api/devices/{id} 返回详情。
- GET /api/devices/management-status 返回 configured、syncing、interval_seconds、stale_seconds、last_synced_at、last_error。
- POST /api/devices/sync 返回 added、updated、missing、conflicts、synced_at；conflicts 为列表。
- POST /api/devices/{id}/link 请求 {peer_id}。
- POST /api/devices/{id}/revoke 撤销直接入网设备。
- GET /api/devices/onboarding 返回管理地址、配置状态、各平台官方安装入口，不返回 PAT。
- GET /api/devices/export?version=2 导出增强清单；POST /import 接受 v1/v2。

响应新增 source、peer_id、connection_status（online/offline/unknown/removed/revoked）、last_seen、synced_at、mesh_groups、gateway_status；不包含上游私密数据。

## 客户端与安装

设备页增加类型/平台/标签编辑筛选、真实组网与网关状态、同步结果和接入指引。明确删除清单与撤销入网的后果。SSH 仅在 access_mode=ssh 时启用；web 仅构造经过校验的 HTTP(S) 地址；none 不显示远控入口。保留搜索、批量检测、导入预览与旧数据兼容。

文档给出云端 Docker/NetBird 配置、各平台安装入口、手机自托管配置、网关配置、备份和验收步骤。本次测试用真实本机 TCP 服务与受控 HTTP 传输；真实云端跨 NAT 和实体设备验收由用户部署后执行。

## 验收

覆盖旧库迁移、元数据/导入/网关/鉴权；节点新增、IP变化、离线、删除、控制面失败与切换；排除与撤销；后台关停；客户端交互；全量后端、前端、类型检查及构建。独立规格审查和代码审查后整合回当前项目。
