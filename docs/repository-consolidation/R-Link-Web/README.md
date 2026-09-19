# lcxinc/R-Link-Web 迁移记录

> 后续变更：已移除云账号、数据库同步和云函数。下文为合并时的历史审查记录；当前启动与访问方式见[项目说明](../../../README.md)。被删除的来源文件仅以 `.source.txt` 保留迁移证据，不参与构建。

## 2026-09-19 整合复核

统一维护入口为本仓库 `apps/r-link-web/`。已核对来源主分支 `9b737e6` 相对初始快照的 15 个变更路径，见 [source-head-review.json](source-head-review.json)。依赖分支意图此前已整合，本次继续保留原件。

来源完整历史已保存为 Git bundle 并通过 `git bundle verify`，SHA-256 见增量核对文件；历史可能含旧本地配置，因此 bundle 位于 Git 忽略的 `.repository-consolidation-local/`。原 `.env` 备份继续保留且未启用。

校验现在针对保存的来源原件：运行文件可继续维护，修改前将来源原件归档并在清单登记。归档仍按原 Git blob 校验，禁止通过更新预期 hash 掩盖损坏。

以下内容为早期迁移阶段的历史记录，其中“待合并/待退役”描述不代表本次最终状态。


来源：`lcxinc/R-Link-Web`，默认分支提交 `f2b95e8c6cf1b1bfa1d234bf64404d6cfb16863a`，树 `a30f75994d272f6bd8ed16e73538c7fee5013c17`。
目标基线：`2408ef4f0c98993c63fbac5f940ab4a30509ada0`，运行目录 `apps/r-link-web/`。

客户端认证、API 端口、SSH 票据和构建问题已修正。服务端 HTTP 路由继续要求认证，WebSocket 使用单独的票据认证；连接注册表提取为 API 与动态插件共用模块。前端 12 项、后端 19 项测试及 Web 构建通过。

## 覆盖范围

共 144 个来源跟踪文件，逐项记录在 [manifest.json](manifest.json)。清单保存原始路径、文件模式、Git blob 和迁移后的路径/hash；调整过的文件在 `originals/` 保存原始字节。归档使用 `.source.txt` 后缀避免被当作配置执行。

- `redacted_local_configuration`: 1
- `migrated_with_adjustment`: 16
- `archived_editor_metadata`: 5
- `migrated`: 122

`.env` 如存在，只提交值已遮蔽的归档，原文保存在迁移机器的 `.repository-consolidation-local/`（Git 忽略）。删除来源前须保留该本地配置备份。没有下载大型数据集。

本记录覆盖固定默认分支的文件快照；不包含完整 Git 历史、其他分支、Issues、Releases 或 GitHub 设置。当前阶段保留来源仓库，PR 合并后重新核对来源 HEAD 与目标默认分支清单，再决定删除。

## Remaining dependency branch review (2026-09-11)

The only additional branch, `deps/fix-wildcards-and-upgrade`, is one commit ahead of the migrated main snapshot and changes only `package.json`. Its complete original file and per-dependency decisions are preserved in [dependency-branch-review.json](dependency-branch-review.json).

The wildcard-removal intent is applied using versions already resolved by the integrated client lockfile: clsx 2.1.1, react-router-dom 7.18.3, react-zoom-pan-pinch 4.2.0, and tailwind-merge 3.6.0. The older proposed router/zoom/merge ranges and lower Supabase minimum are not applied. Existing tested build-tool pins, icon version, Node types, and the framer-motion replacement remain. Removed path/motion dependencies are preserved in the source archive. No installed dependency version changes are intended.

Retirement still requires merging this follow-up PR, checking both remote branch heads again, and preserving the ignored original environment configuration. Full Git history will also be retained in a local bundle before repository retirement. Native Tauri packaging and live Supabase/SSH were not verified.
