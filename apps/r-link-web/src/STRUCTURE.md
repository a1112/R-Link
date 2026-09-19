# 客户端结构

- `App.tsx`：直接挂载管理界面、路由切换与主题状态。
- `api/`：服务 API、可选访问密钥、SSH 短期票据及套接字。
- `components/layout/`：主布局、侧边导航、标题栏。
- `components/pages/`：仪表盘、SSH、网络、存储、插件等页面。
- `components/modals/`：系统设置、服务访问设置、条款说明。
- `components/ui/`：通用界面组件。
- `constants/routes.ts`：导航与页面路由。
- `hooks/`：本地 UI 通用 hooks。
- `utils/`：Tauri 集成。

客户端不再依赖云账号或外部数据库。开发入口及访问配置见[客户端说明](../README.md)。
