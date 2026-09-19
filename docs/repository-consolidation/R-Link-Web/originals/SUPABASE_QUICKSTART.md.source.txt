# Supabase 快速开始

你的 Supabase 已配置完成！

## 配置信息

```
URL: https://pybhmnlimcjrupttaafs.supabase.co
Key: sb_publishable_gyeWIs1cn9VsUs5jLPT1Sg_bRyeM1xY
```

## 安装依赖

```bash
npm install @supabase/supabase-js
```

## 使用方式

### 1. 导入客户端

```tsx
import { supabase } from "@/utils/supabase/client";
```

### 2. 认证功能

```tsx
import { useAuth } from "@/hooks";

function Login() {
  const { signIn, signUp, user, signOut } = useAuth();

  if (user) {
    return <button onClick={signOut}>退出 ({user.email})</button>;
  }

  return (
    <button onClick={() => signIn("user@example.com", "password")}>
      登录
    </button>
  );
}
```

### 3. 数据库操作

```tsx
import { profileApi, pluginConfigApi } from "@/utils";

// 读取用户资料
const profile = await profileApi.getById(userId);

// 更新资料
await profileApi.update(userId, { username: "newname" });

// 插件配置
await pluginConfigApi.upsert(userId, "nginx-plugin", {
  port: 8080,
  enabled: true
});
```

### 4. React Hooks

```tsx
import { useSupabaseQuery, useSupabaseMutation } from "@/hooks";

function MyComponent() {
  // 查询
  const { data, loading } = useSupabaseQuery(
    () => profileApi.getById(userId),
    [userId]
  );

  // 修改
  const { mutate } = useSupabaseMutation(
    (updates) => profileApi.update(userId, updates)
  );

  return <div onClick={() => mutate({ username: "test" })}>{data?.username}</div>;
}
```

## 测试连接

运行开发服务器后，访问测试组件验证连接：

```tsx
import { SupabaseConnectionTest } from "@/components/SupabaseConnectionTest";

function App() {
  return <SupabaseConnectionTest />;
}
```

## 下一步

1. 在 Supabase Dashboard 创建数据表
2. 启用 Row Level Security (RLS)
3. 更新 `src/utils/supabase/types.ts` 中的类型定义

访问你的 Dashboard: https://supabase.com/dashboard/project/pybhmnlimcjrupttaafs
