# Supabase 数据库集成指南

本指南说明如何在 R-Link 项目中使用 Supabase 数据库。

## 目录

1. [环境准备](#环境准备)
2. [项目配置](#项目配置)
3. [数据库表创建](#数据库表创建)
4. [在代码中使用](#在代码中使用)
5. [实时订阅](#实时订阅)
6. [文件存储](#文件存储)

---

## 环境准备

### 1. 创建 Supabase 项目

1. 访问 [https://supabase.com](https://supabase.com)
2. 注册/登录账号
3. 点击 "New Project" 创建新项目
4. 记录以下信息：
   - **Project URL** (如: `https://xxx.supabase.co`)
   - **anon/public key** (公开密钥)
   - **service_role key** (服务端密钥，仅在需要时使用)

### 2. 安装依赖

```bash
cd R-Link-Web
npm install @supabase/supabase-js
```

---

## 项目配置

### 环境变量

创建 `.env` 文件：

```env
# Supabase 配置
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_SUPABASE_SERVICE_ROLE_KEY=your-service-role-key  # 可选，仅服务端使用
```

### 获取类型定义

在 Supabase Dashboard 中：

1. 进入你的项目
2. 点击左侧 API 菜单
3. 找到 "TypeScript definition" 部分
4. 复制生成的类型到 `src/utils/supabase/types.ts`

---

## 数据库表创建

### 方式一：使用 SQL 编辑器

在 Supabase Dashboard -> SQL Editor 中执行：

```sql
-- 用户资料表
CREATE TABLE profiles (
  id UUID REFERENCES auth.users PRIMARY KEY,
  email TEXT NOT NULL,
  username TEXT UNIQUE,
  avatar_url TEXT,
  full_name TEXT,
  role TEXT DEFAULT 'user',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 插件配置表
CREATE TABLE plugin_configs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  plugin_id TEXT NOT NULL,
  config JSONB DEFAULT '{}',
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  UNIQUE(user_id, plugin_id)
);

-- 用户设置表
CREATE TABLE user_settings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE UNIQUE NOT NULL,
  theme TEXT,
  language TEXT DEFAULT 'zh-CN',
  notifications_enabled BOOLEAN DEFAULT true,
  settings JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 启用行级安全策略 (RLS)
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE plugin_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- 策略：用户只能读写自己的数据
CREATE POLICY "Users can view own profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own plugin configs" ON plugin_configs
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own plugin configs" ON plugin_configs
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own settings" ON user_settings
  FOR ALL USING (auth.uid() = user_id);

-- 自动更新 updated_at 的触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = TIMEZONE('utc', NOW());
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_plugin_configs_updated_at BEFORE UPDATE ON plugin_configs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 方式二：使用 Supabase CLI

```bash
# 安装 Supabase CLI
npm install -g supabase

# 初始化本地开发环境
supabase init

# 启动本地数据库
supabase start

# 创建迁移文件
supabase migration new create_tables

# 在迁移文件中添加上面的 SQL

# 应用迁移
supabase db push
```

---

## 在代码中使用

### 认证功能

```tsx
import { useAuth } from "@/hooks/useSupabase";

function MyComponent() {
  const { user, signIn, signUp, signOut, loading } = useAuth();

  if (loading) return <div>加载中...</div>;

  if (!user) {
    return (
      <button onClick={() => signIn("user@example.com", "password")}>
        登录
      </button>
    );
  }

  return (
    <div>
      <p>欢迎, {user.email}</p>
      <button onClick={signOut}>退出</button>
    </div>
  );
}
```

### 数据库操作

```tsx
import { profileApi, pluginConfigApi } from "@/utils/supabase/database";

// 获取用户资料
const profile = await profileApi.getById(userId);

// 更新用户资料
await profileApi.update(userId, {
  username: "newname",
  full_name: "张三"
});

// 获取插件配置
const configs = await pluginConfigApi.getUserConfigs(userId);

// 保存插件配置
await pluginConfigApi.upsert(userId, "nginx-plugin", {
  port: 8080,
  ssl: true
});

// 启用/禁用插件
await pluginConfigApi.setEnabled(userId, "nginx-plugin", false);
```

### 使用 React Hooks

```tsx
import { useSupabaseQuery, useSupabaseMutation } from "@/hooks/useSupabase";

function DataComponent() {
  // 查询数据
  const { data, loading, error, refetch } = useSupabaseQuery(
    async () => await profileApi.getById(userId),
    [userId]
  );

  // 修改数据
  const { mutate: updateProfile, loading: updating } = useSupabaseMutation(
    async (updates) => await profileApi.update(userId, updates)
  );

  if (loading) return <div>加载中...</div>;

  return (
    <div>
      <p>{data?.username}</p>
      <button
        onClick={() => updateProfile({ username: "newname" })}
        disabled={updating}
      >
        更新
      </button>
    </div>
  );
}
```

---

## 实时订阅

Supabase 支持实时数据同步：

```tsx
import { useSupabaseSubscription } from "@/hooks/useSupabase";

function RealtimeComponent() {
  const [messages, setMessages] = useState([]);

  // 订听表的变化
  useSupabaseSubscription(
    "my-channel",
    {
      table: "plugin_configs",
      filter: `user_id=eq.${userId}`,  // 只订阅自己的数据
      event: "*"  // "INSERT" | "UPDATE" | "DELETE" | "*"
    },
    (payload) => {
      console.log("变化:", payload);
      // 处理变化
      if (payload.eventType === "INSERT") {
        setMessages(prev => [...prev, payload.record]);
      }
    }
  );

  return <div>...</div>;
}
```

---

## 文件存储

### 创建存储桶

在 Supabase Dashboard -> Storage -> Create a new bucket：

- 名称: `avatars`
- 公开: true (如果是头像等公开资源)

### 上传文件

```tsx
import { useSupabaseUpload, useSupabasePublicUrl } from "@/hooks/useSupabase";

function UploadComponent() {
  const { upload, loading, progress } = useSupabaseUpload();
  const { getPublicUrl } = useSupabasePublicUrl();

  const handleUpload = async (file: File) => {
    const path = `${userId}/${Date.now()}_${file.name}`;
    await upload("avatars", path, file, { upsert: true });
  };

  const getUrl = (path: string) => {
    return getPublicUrl("avatars", path);
  };
}
```

---

## 安全建议

1. **永远不要在客户端暴露 service_role key**
2. **使用 Row Level Security (RLS)** 保护数据
3. **验证用户输入**，防止 SQL 注入
4. **限制 API 访问频率**，防止滥用

---

## 调试

### 查看请求日志

在 Supabase Dashboard -> Database -> Logs 可以查看所有数据库请求。

### 开启调试模式

```ts
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(url, key, {
  global: {
    headers: {
      // 添加调试头
      "X-Client-Info": "rlink-web",
    },
  },
  // 开启详细日志
  db: { schema: "public" },
});
```

---

## 更多资源

- [Supabase 官方文档](https://supabase.com/docs)
- [Supabase React 指南](https://supabase.com/docs/guides/getting-started/quickstarts/react)
- [Supabase 实时订阅](https://supabase.com/docs/guides/realtime)
- [Supabase 存储](https://supabase.com/docs/guides/storage)
