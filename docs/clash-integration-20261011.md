# Clash / Mihomo 代理集成

R-Link 的“网络管理 → Clash 代理”提供 Clash 兼容控制接口管理。可以接入已运行的 Clash/Mihomo，也可以导入配置后，由 R-Link 启动和停止独立的 Mihomo 进程。所有操作均在 **R-Link API 服务端所在机器**执行；远程服务端的 `127.0.0.1` 指远程机器。

支持控制器连接状态、内核版本、规则/全局/直连模式、日志级别、策略组节点选择、节点延迟测试、规则查看、当前连接与累计流量、单条/全部连接关闭，以及代理集合更新。数据来自内核真实 API，控制器不可达时显示错误。

## 接入现有内核

1. 在 Clash/Mihomo 的配置或 Clash Verge 设置中启用 `external-controller`，例如 `127.0.0.1:9090`，并设置 `secret`。使用实际监听地址和端口。
2. 在 R-Link 的“Clash 代理”页填写 `http://127.0.0.1:9090` 和控制器密钥，保存连接配置。
3. 确认状态显示“已连接”和真实内核版本，再进行模式、节点等操作。

HTTP 控制地址仅接受本机回环；远程控制器使用 HTTPS 和密钥。浏览器只向 R-Link API 发送请求，不直接访问控制器。控制器密钥保存在服务端私有数据目录，列表只返回是否已配置；留空保留原密钥，可显式清除。R-Link 服务访问密钥与 Clash 控制器密钥各自独立。

已经由 Clash Verge 或系统服务启动的内核，通过原客户端启停。R-Link 的独立内核启停操作仅管理自己创建的子进程。Clash Verge 只开放 Unix socket 时，应在其设置中另行启用 HTTP 控制接口。

## 使用独立 Mihomo 内核

按 [Mihomo 官方安装说明](https://wiki.metacubex.one/en/startup/) 安装适合系统及架构的可执行程序，再设置启动 R-Link 服务端时的环境变量：

```sh
export R_LINK_MIHOMO_BINARY='/absolute/path/to/mihomo'
.venv/bin/python R-Link-Server/main.py
```

在已经安装 Clash Verge 的 macOS 上，可以使用它附带的可执行程序，无需复制用户配置：

```sh
export R_LINK_MIHOMO_BINARY='/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo'
.venv/bin/python R-Link-Server/main.py
```

该路径随安装位置和版本变化，以本机实际路径为准。未设置时按服务端的 PATH 和仓库 `binaries/mihomo` 查找；Windows 使用 `mihomo.exe`。第三方内核的许可证及更新由使用者按官方要求处理。

在“独立内核”中填写配置名称，粘贴 YAML 或导入 YAML 文件，保存后启动。R-Link 校验配置，再启动自己的进程；控制接口绑定回环并生成独立密钥。运行配置使用私有目录，不向浏览器返回节点密码、订阅地址或原始 YAML。独立实例使用普通本机代理入口，不申请管理员权限，不启用 TUN 或修改系统代理。

页面中的“受管配置”和“受管内核”对应这一独立实例。服务端为独立实例分配空闲混合端口，覆盖导入配置的 HTTP/SOCKS/混合端口以避开现有 Clash Verge；HTTP 和 SOCKS 均通过这个混合入口使用。控制接口端口单独分配。配置中的额外监听器、透明代理、TUN、DNS 监听和外部控制界面被禁用；代理集合与规则集合的缓存移到该配置的私有目录。引用宿主机文件的提供商需要自行调整为 HTTP 提供商或内联内容。

下面是用于确认内核、策略组和本机代理入口工作的最小配置，只有直连和拒绝策略，不含代理服务器或订阅：

```yaml
mode: rule
log-level: info
proxies: []
proxy-groups:
  - name: 默认策略
    type: select
    proxies:
      - DIRECT
      - REJECT
rules:
  - MATCH,默认策略
```

要使用真实代理节点，在导入配置中添加自己的 `proxies` 或 `proxy-providers`。R-Link 支持更新已有代理集合；不提供订阅转换、从 URL 自动导入完整配置或账号购买。服务端需要能访问相应节点和提供商地址。

内核停止或 R-Link 服务退出时，自有进程关闭；不会关闭现有 Clash Verge。启动独立内核后页面操作针对独立内核，停止后回到已保存的外部控制器配置。配置不会在服务重启时自动启动。

## 接口与部署

全部接口位于 `/api/clash`，沿用 R-Link 本地访问及服务密钥认证。

延迟测试默认使用 `https://www.gstatic.com/generate_204`；可在服务端设置 `R_LINK_CLASH_TEST_URL` 为实际需要测试的 HTTP/HTTPS 地址。测试从所选策略组当前节点发起，结果取决于该节点和测试地址的可达性。

| 路径 | 方法与用途 |
| --- | --- |
| `/settings` | GET / PUT，控制器地址和密钥配置；响应不含密钥 |
| `/status` | GET，控制器连接、版本及独立内核状态 |
| `/configs` | GET / PATCH，基本端口和模式/日志级别 |
| `/proxies` | GET，节点和策略组 |
| `/proxies/{name}` | PUT，选择策略组节点 |
| `/proxies/{name}/delay` | GET，节点延迟；超时参数有上限 |
| `/rules` | GET，内核运行规则 |
| `/connections` | GET / DELETE，连接快照/关闭全部 |
| `/traffic` | GET，带采样时间和来源标识的连接/累计流量快照 |
| `/connections/{id}` | DELETE，关闭指定连接 |
| `/providers/proxies` | GET，代理集合状态和用量 |
| `/providers/proxies/{name}` | PUT，更新已有代理集合 |
| `/profiles` | GET / POST，配置元数据/导入 YAML |
| `/profiles/{id}` | DELETE，删除非运行配置 |
| `/managed/start`、`/managed/stop` | POST，启动指定配置/停止自有内核 |

控制器凭据、配置和运行数据位于 `R_LINK_DATA_DIR`，备份应使用私有访问权限。Unix 上私有文件权限为 0600；Windows 使用服务账号专用目录和 NTFS ACL。

Docker 的 API 服务可以通过 HTTPS 接入外部控制器，或者将对应 Linux Mihomo 可执行文件放入挂载的 `binaries/` 目录。容器中的回环地址只指容器自身；本机代理入口的回环监听不会自动对容器外公开。Compose 不公开新的代理或控制器端口，需要宿主机代理能力时使用本机服务方式。

协议依据：[Mihomo REST API](https://wiki.metacubex.one/en/api/)、[控制接口配置](https://wiki.metacubex.one/en/config/general/)。连接累计流量来自 `/connections` 快照，节点延迟来自内核测试，均不等于目标设备或跨网络实际验收。
“流量管理”页面通过 `/api/clash/traffic` 读取带时间的连接快照，计算真实平均速率并提供筛选、分组汇总和批量断开；见[网络流量管理](traffic-management-20261011.md)。不转发内核 `/traffic`、`/memory` 或 `/logs` 的持续流。

## 验证

```sh
.venv/bin/python -m pytest R-Link-Server -q
npm test
npm run build
R_LINK_RUN_CLASH_INTEGRATION=1 \
R_LINK_MIHOMO_BINARY='/absolute/path/to/mihomo' \
.venv/bin/python -m pytest R-Link-Server/test_clash_integration.py -q
```

真实内核测试使用隔离数据目录和回环端口，验证控制器认证、配置读取、节点切换、节点延迟、普通 HTTP 代理转发、导入端口冲突隔离、HTTP 代理集合更新与自有进程退出。不会改动系统代理、现有 Clash Verge 或用户订阅。

2026-10-11 macOS 验证：服务端 195 项通过，3 项按默认设置跳过；单独启用真实 Mihomo 1.19.32 测试后通过。前端 57 项、桌面窗口行为 12 项通过，TypeScript 检查与生产构建通过。浏览器实测导入最小 YAML、启动独立内核并读取中文策略组成功。测试配置与独立测试进程已清理。未验证用户真实订阅、Windows/Linux 运行或 TUN。
