# Linux 网关设备限速与 QoS

在“流量管理”的“设备 QoS”中配置网关面向设备的接口、网关总带宽及每个设备的 IP 策略。所有上传/下载方向均相对于设备：设备上传经所选接口入口，设备下载经所选接口出口。

执行点是运行 R-Link API 的 Linux 网关。设备的流量必须实际经过该接口，并且此处能看到策略中的设备 IP。设备清单、NetBird 在线状态或 Clash 连接记录本身不会改变流量路径。此功能不自动开启转发、设置 NAT、修改路由或把已有主机变成网关。

## 限速与优先级

采用 Linux `tc`：下载在所选接口使用 HTB；上传通过入口重定向到本服务创建的 IFB，再使用 HTB。按设备 IPv4/IPv6 地址分类，支持最多 64 条设备策略。

- 总带宽是经过该接口的流量可共享的上传/下载上限，包括未匹配设备策略的流量。
- 每设备上限限制该设备在对应方向的吞吐；留空表示使用网关总上限。
- 每设备保障带宽是竞争时的 HTB `rate`；上限对应 `ceil`。已启用策略的保障带宽之和不能超过网关总量，需给默认类保留 0.001 Mbps。
- 高、普通、低对应 HTB 优先级 0、3、7，在各类使用其保障带宽后，决定借用剩余带宽的顺序。该优先级不承诺端到端时延，也不设置 DSCP。
- 禁用某条设备策略后，该地址进入默认类，仍受网关总上限限制。停用整个 QoS 会移除本服务拥有的整形对象。

IP 应填写接口上实际可见的设备地址；设备名只用于标识。登记主机名不会自动解析或追随 DHCP 变化。地址变化时需更新策略；删除设备清单项也不会自动删除其 IP 策略。

当前限速单位是每条 IP 策略。同一设备同时使用多个 IPv4/IPv6 地址时，需分别建立策略，各地址的带宽独立计数；绑定设备清单项只用于辅助填写，不合并多个地址的总带宽。

## 保存与生效

“保存策略”只保存期望配置，不改变网络。页面分别展示保存版本和生效版本；修改未保存、保存后待应用、执行错误和内核确认生效是不同状态。

“应用到网关”会先检查执行能力及现有网卡配置，再建立整形对象，并复核内核状态。客户端使用保存版本避免并发操作覆盖新策略。现有用户配置的 qdisc、入口过滤器或 IFB 冲突时拒绝接管。更新失败会尝试恢复上一次本服务配置；恢复失败明确报告错误。

QoS 配置独立保存在服务数据目录。正常退出服务时保留内核中的限制；重启后核对内核状态，不能仅凭数据库记录显示生效。系统重启、外部修改或网卡重建可能使策略失效，需重新应用。停用操作保留已保存策略，且仅清理能确认属于本服务的对象。

内核命令与数据文件无法作为单个原子事务提交。异常退出或数据盘故障导致归属证据不完整时，服务报告错误并保留现场，需要网关管理员检查。已确认归属的部分清理可按清理记录版本重试。

## Linux 执行环境

需要 Linux、`iproute2` 的 `tc`/`ip`、内核 HTB/IFB/flower/mirred 支持，以及 `CAP_NET_ADMIN` 或相应 root 权限。设置 `R_LINK_QOS_ENABLED=true` 才允许执行。本机 macOS 可以准备并保存策略，页面会说明无法执行的原因；不能在 macOS 上显示 Linux 策略已生效。

原生 systemd 部署可在已有 `rlink` 服务的覆盖配置中添加：

```ini
[Service]
Environment=R_LINK_QOS_ENABLED=true
AmbientCapabilities=CAP_NET_BIND_SERVICE CAP_NET_ADMIN
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_NET_ADMIN
```

安装系统 `iproute2`，由网关管理员准备 IFB 内核支持，重新加载 systemd 并重启服务后，在页面选择客户端侧接口。现有接口应为本服务允许接管的默认根队列，且没有其他入口整形规则。服务访问密钥配置仍按原有部署要求执行。

默认 Docker Compose 使用独立容器网络和普通用户，不能管理主机网卡。Linux 网关可明确启用独立覆盖文件：

```sh
docker compose --env-file deploy/.env \
  -f deploy/compose.yaml -f deploy/compose.qos.yaml up -d --build
```

此覆盖文件要求支持 `!reset` 的 Docker Compose 版本，使服务与网页使用 Linux 主机网络，并只在回环地址提供 API `8210` 与网页 `8080`。服务以 root 运行，但仅保留网卡管理及现有数据卷访问所需的权限。不要在 Docker Desktop 虚拟机里将其当作物理网关部署；必须选择真正承载设备流量的 Linux 主机。

## 接口与验证

所有接口沿用管理服务认证：

| 方法与路径 | 用途 |
| --- | --- |
| `GET /api/qos/status` | 执行能力、网卡、期望/生效版本、内核状态与统计 |
| `PUT /api/qos/config` | 带 `expected_revision` 保存完整配置 |
| `POST /api/qos/apply` | 带 `expected_revision` 应用当前保存配置 |
| `DELETE /api/qos/applied?expected_revision=N` | 按应用/清理记录版本停用本服务整形，保留期望配置 |

执行命令使用固定参数数组、超时与有界输出；不调用 shell、sudo 或外部脚本。配置校验拒绝无效/重复 IP、非法接口名和超出总量的保障带宽。

停用确认绑定当前应用记录版本；旧确认不能删除更新后的策略。部分清理失败时返回 `cleanup_revision`，页面允许按该记录重试。清理完成后，已保存配置仍然显示“等待应用”。

真实内核验收使用 Debian Linux 的三个临时网络命名空间，分别模拟设备、转发网关和上游；测试结束后自动删除。验收覆盖 IPv4/IPv6 双向限速、竞争优先级、服务重启后的状态核验、外部配置漂移、停用恢复及拒绝覆盖已有队列。可在专用 Linux 测试机执行：

```sh
sudo env R_LINK_RUN_QOS_INTEGRATION=1 .venv/bin/python \
  -m pytest R-Link-Server/test_qos_integration.py -q -s
```

需预先安装 `iproute2`、`iperf3` 和 `R-Link-Server/requirements-test.txt` 的 Python 依赖。仓库工作流已加入相同验收任务。虚拟网卡测试证明整形执行及协议路径；真实设备上线仍需在承载其流量的 Linux 网关选择正确接口并验收。

2026-10-11 在 Debian 13、Linux 6.12.111 的隔离环境通过真实内核验收：下载上限 2 Mbps、上传上限 3 Mbps 时，IPv4 实测 1.887/2.913 Mbps，IPv6 实测 1.891/2.912 Mbps。6 Mbps 总量竞争时，高/低优先级的应用吞吐约 5.243/0.150 Mbps。应用吞吐包含协议开销，不能作为端到端时延或物理线路容量的承诺。

本次还验证了默认分类漂移、额外 flower 匹配键、异常 mirror action、清理命令失败后恢复，以及清理重试保留外部新增 class。常规后端测试为 232 通过、5 跳过；前端 89 项、桌面窗口 12 项及生产构建通过。源码保留记录核验和 Compose/nginx 配置核验通过。尚未在实际设备网关部署，也未执行 Docker 镜像构建或远端 CI。

参考：[Linux HTB 手册](https://man7.org/linux/man-pages/man8/tc-htb.8.html)、[flower 分类器](https://man7.org/linux/man-pages/man8/tc-flower.8.html)、[mirred 重定向](https://man7.org/linux/man-pages/man8/tc-mirred.8.html)。
