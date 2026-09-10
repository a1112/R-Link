# R-Link 前端 API 文档

## 概述

此目录包含 R-Link 前端的 API 客户端代码，用于与后端 FastAPI 服务通信。

## 目录结构

```
src/api/
├── index.ts      # 统一导出入口
├── types.ts      # TypeScript 类型定义
├── config.ts     # API 配置
├── client.ts     # HTTP 客户端封装
├── plugins.ts    # 插件相关 API
├── system.ts     # 系统相关 API
└── hooks.ts      # React Hooks
```

## 使用方法

### 1. 直接使用 API 类

```typescript
import { pluginsApi, systemApi } from '@/api';

// 获取插件列表
const plugins = await pluginsApi.list();

// 获取系统资源
const resources = await systemApi.getResources();

// 启动插件
await pluginsApi.start('plugin-name');

// 停止插件
await pluginsApi.stop('plugin-name');
```

### 2. 使用 React Hooks

```typescript
import { usePlugins, useSystemResources } from '@/api';

function MyComponent() {
  // 获取插件列表（自动轮询刷新）
  const { data: plugins, loading, error, refetch } = usePlugins();

  // 获取系统资源（每 5 秒刷新）
  const { data: resources } = useSystemResources(5000);

  // 获取单个插件状态
  const { data: status } = usePluginStatus('plugin-name', 3000);

  // 插件操作
  const { start, stop, restart, loading: actionLoading } = usePluginActions();

  return (
    <div>
      {/* 渲染组件 */}
    </div>
  );
}
```

## API 端点

### 插件 API (`/api/plugins/`)

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/` | 获取所有插件列表 |
| GET | `/{name}` | 获取指定插件信息 |
| POST | `/{name}/start` | 启动插件 |
| POST | `/{name}/stop` | 停止插件 |
| POST | `/{name}/restart` | 重启插件 |
| GET | `/{name}/status` | 获取插件状态 |
| GET | `/status/all` | 获取所有插件状态 |
| GET | `/{name}/config` | 获取插件配置 |
| PUT | `/{name}/config` | 设置插件配置 |
| GET | `/{name}/logs` | 获取插件日志 |
| GET | `/{name}/health` | 检查插件健康状态 |

### 系统 API (`/api/system/`)

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/info` | 获取系统信息 |
| GET | `/resources` | 获取系统资源使用情况 |
| GET | `/processes` | 获取系统进程列表 |
| GET | `/uptime` | 获取系统运行时间 |

### 通用 API

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | 根路径，返回服务信息 |

## 类型定义

### PluginInfo
```typescript
interface PluginInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  binary_path: string;
  config_path?: string;
  icon?: string;
}
```

### PluginStatus
```typescript
interface PluginStatus {
  status: 'stopped' | 'running' | 'error';
  pid?: number;
  port?: number;
  uptime: number;
  memory_usage: number;
  cpu_usage: number;
  last_error?: string;
}
```

### SystemResources
```typescript
interface SystemResources {
  cpu: {
    percent: number;
    count: number;
  };
  memory: {
    total: number;
    available: number;
    percent: number;
    used: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
    percent: number;
  };
}
```

## 配置

API 基础 URL 通过 `vite.config.ts` 中的代理配置：

```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    secure: false,
    ws: true,
  },
}
```

环境变量：
- `VITE_API_BASE_URL`: 可选，覆盖默认的 `/api` 基础路径

## 错误处理

API 调用失败时会抛出错误，建议使用 try-catch 处理：

```typescript
try {
  await pluginsApi.start('plugin-name');
  toast.success('插件启动成功');
} catch (error) {
  if (error instanceof Error) {
    toast.error(error.message);
  }
}
```

## Hooks 参数

### useSystemResources
```typescript
useSystemResources(pollInterval?: number)
```
- `pollInterval`: 轮询间隔（毫秒），默认 5000，设为 0 禁用轮询

### usePluginStatus
```typescript
usePluginStatus(name: string, pollInterval?: number)
```
- `name`: 插件名称
- `pollInterval`: 轮询间隔（毫秒），默认 5000
