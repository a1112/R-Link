/**
 * Supabase 认证封装
 * 提供用户登录、注册、会话管理等功能
 */

import { supabase } from "./client";
import type { AuthError, Session, User, Provider } from "@supabase/supabase-js";

export interface AuthState {
  session: Session | null;
  user: User | null;
  loading: boolean;
}

export interface SignInCredentials {
  email: string;
  password: string;
}

export interface SignUpCredentials {
  email: string;
  password: string;
  username?: string;
  fullName?: string;
}

// ============================================================
// 认证操作
// ============================================================

export const authApi = {
  /**
   * 获取当前会话
   */
  async getSession() {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error) throw error;
    return session;
  },

  /**
   * 获取当前用户
   */
  async getUser() {
    const { data: { user }, error } = await supabase.auth.getUser();
    if (error) throw error;
    return user;
  },

  /**
   * 邮箱密码登录
   */
  async signInWithPassword({ email, password }: SignInCredentials) {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) throw error;
    return data;
  },

  /**
   * 注册新用户
   */
  async signUp({ email, password, username, fullName }: SignUpCredentials) {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          username,
          full_name: fullName,
        },
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (error) throw error;
    return data;
  },

  /**
   * 发送密码重置邮件
   */
  async resetPassword(email: string) {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/reset-password`,
    });

    if (error) throw error;
  },

  /**
   * 更新密码
   */
  async updatePassword(newPassword: string) {
    const { error } = await supabase.auth.updateUser({
      password: newPassword,
    });

    if (error) throw error;
  },

  /**
   * OAuth 社交登录
   */
  async signInWithOAuth(provider: Provider) {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: {
          access_type: "offline",
          prompt: "consent",
        },
      },
    });

    if (error) throw error;
    return data;
  },

  /**
   * 退出登录
   */
  async signOut() {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  },

  /**
   * 监听认证状态变化
   */
  onAuthStateChange(
    callback: (event: "INITIAL_SESSION" | "SIGNED_IN" | "SIGNED_OUT" | "TOKEN_REFRESHED", session: Session | null) => void
  ) {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      callback(_event, session);
    });

    return subscription;
  },
};

// ============================================================
// React Hooks
// ============================================================

/**
 * 认证状态管理 Hook
 */
export const createAuthStore = () => {
  let state: AuthState = {
    session: null,
    user: null,
    loading: true,
  };

  const listeners = new Set<(state: AuthState) => void>();

  const notify = () => {
    listeners.forEach((listener) => listener(state));
  };

  // 初始化会话
  const init = async () => {
    try {
      const session = await authApi.getSession();
      state = {
        session,
        user: session?.user ?? null,
        loading: false,
      };
      notify();
    } catch (error) {
      state = {
        session: null,
        user: null,
        loading: false,
      };
      notify();
    }
  };

  // 监听认证状态变化
  authApi.onAuthStateChange((event, session) => {
    state = {
      session,
      user: session?.user ?? null,
      loading: false,
    };
    notify();
  });

  return {
    getState: () => state,
    subscribe: (listener: (state: AuthState) => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    signIn: async (credentials: SignInCredentials) => {
      const { session } = await authApi.signInWithPassword(credentials);
      if (session) {
        state.session = session;
        state.user = session.user;
        notify();
      }
    },
    signUp: async (credentials: SignUpCredentials) => {
      const data = await authApi.signUp(credentials);
      if (data.session) {
        state.session = data.session;
        state.user = data.session.user;
        notify();
      }
      return data;
    },
    signOut: async () => {
      await authApi.signOut();
      state.session = null;
      state.user = null;
      notify();
    },
    init,
  };
};

// 导出全局实例
export const authStore = createAuthStore();
