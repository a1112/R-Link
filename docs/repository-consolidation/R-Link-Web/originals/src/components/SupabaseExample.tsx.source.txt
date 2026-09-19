/**
 * Supabase 集成示例组件
 * 展示如何在组件中使用 Supabase 数据库和认证
 */

import React, { useState } from "react";
import { useAuth, useSupabaseQuery, useSupabaseMutation } from "../hooks/useSupabase";
import { profileApi, pluginConfigApi } from "../utils/supabase/database";

/**
 * 示例 1: 用户认证组件
 */
export const AuthExample: React.FC = () => {
  const { user, session, loading, signIn, signUp, signOut } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLogin, setIsLogin] = useState(true);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (isLogin) {
        await signIn(email, password);
      } else {
        await signUp(email, password, email.split("@")[0]);
      }
    } catch (error: any) {
      alert(error.message);
    }
  };

  if (loading) {
    return <div>加载中...</div>;
  }

  if (user) {
    return (
      <div className="p-4 bg-[var(--c-900)] rounded-lg">
        <h3 className="text-lg font-bold mb-2">欢迎, {user.email}</h3>
        <p className="text-sm text-[var(--c-500)] mb-4">用户 ID: {user.id}</p>
        <button
          onClick={() => signOut()}
          className="px-4 py-2 bg-red-500 text-white rounded"
        >
          退出登录
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleAuth} className="p-4 bg-[var(--c-900)] rounded-lg space-y-4">
      <h3 className="text-lg font-bold">{isLogin ? "登录" : "注册"}</h3>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="邮箱"
        className="w-full px-3 py-2 bg-[var(--c-800)] rounded text-white"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="密码"
        className="w-full px-3 py-2 bg-[var(--c-800)] rounded text-white"
        required
      />
      <button
        type="submit"
        className="w-full px-4 py-2 bg-blue-500 text-white rounded"
      >
        {isLogin ? "登录" : "注册"}
      </button>
      <button
        type="button"
        onClick={() => setIsLogin(!isLogin)}
        className="w-full text-sm text-[var(--c-500)]"
      >
        {isLogin ? "没有账号？注册" : "已有账号？登录"}
      </button>
    </form>
  );
};

/**
 * 示例 2: 读取用户数据
 */
export const UserProfileExample: React.FC = () => {
  const { user } = useAuth();

  // 使用 useSupabaseQuery 获取用户资料
  const { data: profile, loading, error, refetch } = useSupabaseQuery(
    async () => {
      if (!user) throw new Error("未登录");
      return await profileApi.getById(user.id);
    },
    [user?.id]
  );

  if (!user) {
    return <div>请先登录</div>;
  }

  if (loading) {
    return <div>加载中...</div>;
  }

  if (error) {
    return <div>错误: {error.message}</div>;
  }

  return (
    <div className="p-4 bg-[var(--c-900)] rounded-lg">
      <h3 className="text-lg font-bold mb-4">用户资料</h3>
      {profile ? (
        <div className="space-y-2">
          <p>邮箱: {profile.email}</p>
          <p>用户名: {profile.username || "未设置"}</p>
          <p>全名: {profile.full_name || "未设置"}</p>
          <p>角色: {profile.role || "user"}</p>
        </div>
      ) : (
        <p className="text-[var(--c-500)]">暂无资料</p>
      )}
      <button
        onClick={() => refetch()}
        className="mt-4 px-4 py-2 bg-blue-500 text-white rounded"
      >
        刷新
      </button>
    </div>
  );
};

/**
 * 示例 3: 更新用户数据
 */
export const UpdateProfileExample: React.FC = () => {
  const { user } = useAuth();
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");

  // 使用 useSupabaseMutation 更新用户资料
  const { mutate: updateProfile, loading, error } = useSupabaseMutation(
    async (updates: { username?: string; full_name?: string }) => {
      if (!user) throw new Error("未登录");
      return await profileApi.update(user.id, updates);
    }
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await mutate({ username, full_name: fullName });
      alert("更新成功！");
    } catch (error: any) {
      alert(error.message);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 bg-[var(--c-900)] rounded-lg space-y-4">
      <h3 className="text-lg font-bold">更新资料</h3>
      <input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="用户名"
        className="w-full px-3 py-2 bg-[var(--c-800)] rounded text-white"
      />
      <input
        type="text"
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
        placeholder="全名"
        className="w-full px-3 py-2 bg-[var(--c-800)] rounded text-white"
      />
      <button
        type="submit"
        disabled={loading}
        className="w-full px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50"
      >
        {loading ? "保存中..." : "保存"}
      </button>
      {error && <p className="text-red-500 text-sm">{error.message}</p>}
    </form>
  );
};

/**
 * 示例 4: 插件配置管理
 */
export const PluginConfigExample: React.FC = () => {
  const { user } = useAuth();
  const [selectedPlugin, setSelectedPlugin] = useState<string>("nginx-plugin");
  const [configJson, setConfigJson] = useState("{}");

  // 获取用户的所有插件配置
  const { data: configs, refetch } = useSupabaseQuery(
    async () => {
      if (!user) throw new Error("未登录");
      return await pluginConfigApi.getUserConfigs(user.id);
    },
    [user?.id]
  );

  // 保存插件配置
  const { mutate: saveConfig, loading: saving } = useSupabaseMutation(
    async (pluginId: string) => {
      if (!user) throw new Error("未登录");
      const config = JSON.parse(configJson);
      return await pluginConfigApi.upsert(user.id, pluginId, config);
    }
  );

  // 切换插件启用状态
  const { mutate: toggleEnabled } = useSupabaseMutation(
    async ({ pluginId, enabled }: { pluginId: string; enabled: boolean }) => {
      if (!user) throw new Error("未登录");
      return await pluginConfigApi.setEnabled(user.id, pluginId, enabled);
    }
  );

  if (!user) {
    return <div>请先登录</div>;
  }

  return (
    <div className="p-4 bg-[var(--c-900)] rounded-lg space-y-4">
      <h3 className="text-lg font-bold">插件配置管理</h3>

      {/* 配置列表 */}
      <div className="space-y-2">
        {configs?.map((cfg) => (
          <div
            key={`${cfg.plugin_id}-${cfg.user_id}`}
            className="flex items-center justify-between p-2 bg-[var(--c-800)] rounded"
          >
            <span>{cfg.plugin_id}</span>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-1 rounded ${cfg.enabled ? "bg-green-500" : "bg-red-500"}`}>
                {cfg.enabled ? "启用" : "禁用"}
              </span>
              <button
                onClick={() => toggleEnabled({ pluginId: cfg.plugin_id, enabled: !cfg.enabled })}
                className="text-xs px-2 py-1 bg-blue-500 rounded"
              >
                切换
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* 添加/编辑配置 */}
      <div className="space-y-2 border-t border-[var(--c-800)] pt-4">
        <input
          type="text"
          value={selectedPlugin}
          onChange={(e) => setSelectedPlugin(e.target.value)}
          placeholder="插件 ID"
          className="w-full px-3 py-2 bg-[var(--c-800)] rounded text-white"
        />
        <textarea
          value={configJson}
          onChange={(e) => setConfigJson(e.target.value)}
          placeholder='配置 JSON (例如: {"port": 8080})'
          className="w-full px-3 py-2 bg-[var(--c-800)] rounded text-white font-mono text-sm"
          rows={4}
        />
        <button
          onClick={() => saveConfig(selectedPlugin)}
          disabled={saving}
          className="w-full px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50"
        >
          {saving ? "保存中..." : "保存配置"}
        </button>
      </div>

      <button onClick={() => refetch()} className="w-full text-sm text-[var(--c-500)]">
        刷新列表
      </button>
    </div>
  );
};

/**
 * 示例 5: 实时订阅
 */
export const RealtimeExample: React.FC = () => {
  const { user } = useAuth();
  const [logs, setLogs] = useState<string[]>([]);

  // 使用 useSupabaseSubscription 订听变化
  const { useSupabaseSubscription } = require("../hooks/useSupabase");

  useSupabaseSubscription(
    "user_settings_changes",
    {
      table: "user_settings",
      filter: user ? `user_id=eq.${user.id}` : undefined,
    },
    (payload: any) => {
      const log = `[${payload.eventType}] ${new Date().toLocaleTimeString()}`;
      setLogs((prev) => [log, ...prev].slice(0, 10));
    }
  );

  return (
    <div className="p-4 bg-[var(--c-900)] rounded-lg">
      <h3 className="text-lg font-bold mb-4">实时订阅日志</h3>
      <p className="text-sm text-[var(--c-500)] mb-4">
        当 user_settings 表的数据变化时，这里会显示实时日志
      </p>
      <div className="space-y-1">
        {logs.length === 0 ? (
          <p className="text-[var(--c-600)]">等待事件...</p>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="text-sm font-mono text-[var(--c-400)]">
              {log}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

/**
 * 完整示例页面
 */
export const SupabaseExamplesPage: React.FC = () => {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Supabase 集成示例</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AuthExample />
        <UserProfileExample />
        <UpdateProfileExample />
        <PluginConfigExample />
      </div>

      <RealtimeExample />
    </div>
  );
};
