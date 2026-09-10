/**
 * Supabase 客户端配置
 * 用于访问 Supabase 数据库和认证服务
 */

import { createClient } from "@supabase/supabase-js";
import type { Database } from "./types";

// Supabase 项目配置
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || "https://pybhmnlimcjrupttaafs.supabase.co";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || "sb_publishable_gyeWIs1cn9VsUs5jLPT1Sg_bRyeM1xY";

/**
 * 创建 Supabase 客户端实例
 */
export const supabase = createClient<Database>(supabaseUrl, supabaseAnonKey, {
  auth: {
    // 自动刷新 token
    autoRefreshToken: true,
    // 检测会话变化
    detectSessionInUrl: true,
    // 持久化会话
    persistSession: true,
    // 存储键名
    storageKey: "rlink-auth-token",
    // 存储方式（使用 localStorage）
    storage: window.localStorage,
  },
  // 全局请求配置
  global: {
    headers: {
      "X-Client-Info": "rlink-web",
    },
  },
  // 实时订阅配置
  realtime: {
    params: {
      eventsPerSecond: 10,
    },
  },
});

/**
 * Supabase Admin 客户端（需要 service_role key，仅在服务端使用）
 */
export const createAdminClient = () => {
  const serviceRoleKey = import.meta.env.VITE_SUPABASE_SERVICE_ROLE_KEY;
  if (!serviceRoleKey) {
    throw new Error("Service role key is not available in client environment");
  }
  return createClient<Database>(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
};

export default supabase;
