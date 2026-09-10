# Supabase 数据库表创建

## 执行步骤

1. 打开 Supabase Dashboard: https://supabase.com/dashboard/project/pybhmnlimcjrupttaafs

2. 点击左侧菜单 **SQL Editor**

3. 点击 **New Query** 创建新查询

4. 复制 `001_initial_tables.sql` 文件的全部内容，粘贴到编辑器

5. 点击 **Run** 或按 `Ctrl+Enter` 执行

## 创建的表

| 表名 | 说明 |
|------|------|
| `profiles` | 用户扩展信息 |
| `plugin_configs` | 用户插件配置 |
| `plugin_market` | 插件市场 |
| `plugin_reviews` | 插件评论 |
| `user_settings` | 用户设置 |
| `remote_connections` | 远程连接配置 |
| `connection_history` | 连接历史 |
| `frp_configs` | FRP 配置 |
| `storage_mappings` | 存储映射 |
| `notifications` | 通知 |
| `api_keys` | API 密钥 |
| `files` | 文件记录 |
| `audit_logs` | 审计日志 |
| `system_config` | 系统配置 |

## 安全特性

- ✅ 启用行级安全策略 (RLS)
- ✅ 用户只能访问自己的数据
- ✅ 自动创建用户资料 (触发器)
- ✅ 自动更新 updated_at (触发器)
- ✅ 实时订阅支持
