# R-Link 前端代码结构说明

## 目录结构

```
src/
├── api/                    # API 客户端模块
│   ├── index.ts           # 统一导出
│   ├── types.ts           # TypeScript 类型定义
│   ├── config.ts          # API 配置
│   ├── client.ts          # HTTP 客户端封装
│   ├── plugins.ts         # 插件 API
│   ├── system.ts          # 系统 API
│   ├── hooks.ts           # API React Hooks
│   └── README.md          # API 使用文档
│
├── components/            # 组件模块
│   ├── common/            # 通用 UI 组件
│   │   ├── index.ts       # 统一导出
│   │   ├── StatCard.tsx   # 统计卡片
│   │   ├── StatusBadge.tsx # 状态徽章
│   │   ├── FileIcon.tsx   # 文件图标
│   │   └── SidebarItem.tsx # 侧边栏项
│   │
│   ├── layout/            # 布局组件
│   │   ├── index.ts       # 统一导出
│   │   ├── Sidebar.tsx    # 侧边栏
│   │   ├── Header.tsx     # 顶部导航栏
│   │   └── MainLayout.tsx # 主布局
│   │
│   ├── pages/             # 页面组件
│   │   ├── index.ts       # 统一导出
│   │   ├── AuthScreen.tsx # 认证页面
│   │   ├── RemoteView.tsx # 远程设备
│   │   ├── FRPView.tsx    # 隧道管理
│   │   ├── DomainView.tsx # 域名管理
│   │   └── StorageView.tsx # 文件管理
│   │
│   ├── modals/            # 弹窗组件
│   │   ├── index.ts       # 统一导出
│   │   ├── UserMenu.tsx   # 用户菜单
│   │   └── SettingsModal.tsx # 设置弹窗
│   │
│   ├── ui/                # UI 组件库（Radix UI）
│   ├── TopologyView.tsx   # 网络拓扑视图
│   ├── NodeDetailModal.tsx # 节点详情弹窗
│   ├── PluginDetailModal.tsx # 插件详情弹窗
│   ├── DashboardView.tsx  # 仪表盘（API 版）
│   └── PluginsView.tsx    # 插件管理（API 版）
│
├── constants/             # 常量配置
│   ├── index.ts           # 统一导出
│   ├── theme.ts           # 主题配置
│   ├── routes.ts          # 路由配置
│   └── mockData.ts        # 模拟数据
│
├── hooks/                 # 自定义 React Hooks
│   └── index.ts           # Hooks 定义
│
├── supabase/              # Supabase 相关
├── App.tsx                # 主应用（原版）
├── App.new.tsx            # 主应用（重构版）
├── main.tsx               # 应用入口
└── guidelines/            # 设计指南
```

## 组件分类

### 1. 通用 UI 组件 (`components/common/`)

可复用的基础组件，不包含业务逻辑：

- **StatCard** - 统计数据卡片，用于仪表盘等页面
- **StatusBadge** - 状态徽章，显示在线/离线等状态
- **FileIcon** - 文件类型图标
- **SidebarItem** - 侧边栏菜单项

### 2. 布局组件 (`components/layout/`)

应用框架级组件：

- **Sidebar** - 侧边栏导航，包含菜单项和用户信息
- **Header** - 顶部导航栏，包含搜索和用户菜单
- **MainLayout** - 主布局容器，组合 Sidebar 和 Header

### 3. 页面组件 (`components/pages/`)

具体功能页面：

- **AuthScreen** - 登录/注册页面
- **RemoteView** - 远程设备管理
- **FRPView** - 内网穿透隧道管理
- **DomainView** - 域名管理
- **StorageView** - 文件存储管理

### 4. 弹窗组件 (`components/modals/`)

各类弹窗和对话框：

- **UserMenu** - 用户菜单下拉
- **SettingsModal** - 系统设置弹窗

### 5. 专用视图组件

- **TopologyView** - 网络拓扑可视化
- **DashboardView** - 仪表盘（使用真实 API）
- **PluginsView** - 插件管理（使用真实 API）

## 常量配置 (`constants/`)

- **theme.ts** - 主题颜色配置
- **routes.ts** - 路由和菜单配置
- **mockData.ts** - 模拟数据

## 自定义 Hooks (`hooks/`)

- **useBackNavigation** - 浏览器后退导航处理
- **useTheme** - 主题管理
- **useKeyboard** - 键盘快捷键
- **useDebounce** - 防抖处理
- **useLocalStorage** - 本地存储

## 使用示例

### 添加新的页面组件

1. 在 `components/pages/` 创建新组件
2. 在 `components/pages/index.ts` 导出
3. 在 `constants/routes.ts` 添加路由配置
4. 在 `App.tsx` 的路由处理中使用

```typescript
// 1. 创建组件
export const NewView: React.FC = () => {
  return <div>新页面</div>;
};

// 2. 在 routes.ts 添加
{ id: 'new', label: '新页面', icon: Icon, title: '新页面' },

// 3. 在 App.tsx 使用
case 'new':
  return <NewView />;
```

### 使用通用组件

```typescript
import { StatCard, StatusBadge, SidebarItem } from '@/components/common';

// 统计卡片
<StatCard
  title="在线设备"
  value="3"
  sub="总计 4 台"
  icon={Monitor}
  trend="up"
/>

// 状态徽章
<StatusBadge status="online" />

// 侧边栏项
<SidebarItem
  icon={Icon}
  label="菜单项"
  active={false}
  onClick={() => {}}
  collapsed={false}
/>
```

### 使用布局组件

```typescript
import { MainLayout } from '@/components/layout';

<MainLayout
  activeRoute="dashboard"
  onRouteChange={(route) => setActiveTab(route)}
  isGuest={false}
  currentTheme="zinc"
  onThemeChange={setTheme}
  onLogout={handleLogout}
>
  {/* 页面内容 */}
</MainLayout>
```

## 迁移说明

旧的 `App.tsx` 仍然保留，新的重构版本在 `App.new.tsx`。

要使用新版本：

1. 备份旧的 `App.tsx`
2. 将 `App.new.tsx` 重命名为 `App.tsx`
3. 确保所有导入路径正确

## 设计原则

1. **单一职责** - 每个组件只负责一个功能
2. **可复用性** - 通用组件可在多个页面使用
3. **类型安全** - 完整的 TypeScript 类型定义
4. **导出管理** - 每个目录有 index.ts 统一导出
5. **路径别名** - 使用 `@/` 指向 src 目录
