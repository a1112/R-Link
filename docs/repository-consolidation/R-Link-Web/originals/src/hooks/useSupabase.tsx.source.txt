/**
 * Supabase React Hooks
 * 用于在 React 组件中使用 Supabase 功能
 */

import { useEffect, useState, useCallback, useRef } from "react";
import { authStore, authApi } from "../utils/supabase/auth";
import type { User, Session } from "@supabase/supabase-js";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { supabase } from "../utils/supabase/client";

// ============================================================
// 认证 Hooks
// ============================================================

export interface UseAuthReturn {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, username?: string) => Promise<void>;
  signOut: () => Promise<void>;
  signInWithOAuth: (provider: "google" | "github" | "discord") => Promise<void>;
}

/**
 * 认证状态 Hook
 */
export const useAuth = (): UseAuthReturn => {
  const [state, setState] = useState(authStore.getState());
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    // 初始化
    if (!initialized) {
      authStore.init();
      setInitialized(true);
    }

    // 订阅状态变化
    const unsubscribe = authStore.subscribe(setState);
    return unsubscribe;
  }, [initialized]);

  const signIn = useCallback(async (email: string, password: string) => {
    await authStore.signIn({ email, password });
  }, []);

  const signUp = useCallback(async (email: string, password: string, username?: string) => {
    await authStore.signUp({ email, password, username });
  }, []);

  const signOut = useCallback(async () => {
    await authStore.signOut();
  }, []);

  const signInWithOAuth = useCallback(async (provider: "google" | "github" | "discord") => {
    await authApi.signInWithOAuth(provider);
  }, []);

  return {
    user: state.user,
    session: state.session,
    loading: state.loading,
    signIn,
    signUp,
    signOut,
    signInWithOAuth,
  };
};

/**
 * 受保护路由 Hook
 */
export const useRequireAuth = (redirectTo = "/auth") => {
  const { user, loading } = useAuth();
  const [redirecting, setRedirecting] = useState(false);

  useEffect(() => {
    if (!loading && !user && !redirecting) {
      setRedirecting(true);
      window.location.href = redirectTo;
    }
  }, [user, loading, redirecting, redirectTo]);

  return { user, loading, isAuthenticated: !!user };
};

// ============================================================
// 数据库 Hooks
// ============================================================

/**
 * 通用查询 Hook
 */
export const useSupabaseQuery = <T>(
  queryFn: () => Promise<T>,
  deps: any[] = []
) => {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await queryFn();
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
};

/**
 * 通用 mutation Hook
 */
export const useSupabaseMutation = <T, A extends any[] = []>(
  mutationFn: (...args: A) => Promise<T>
) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<T | null>(null);

  const mutate = useCallback(
    async (...args: A) => {
      setLoading(true);
      setError(null);
      try {
        const result = await mutationFn(...args);
        setData(result);
        return result;
      } catch (err) {
        setError(err as Error);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [mutationFn]
  );

  return { mutate, loading, error, data };
};

// ============================================================
// 实时订阅 Hooks
// ============================================================

/**
 * 实时订阅 Hook
 */
export const useSupabaseSubscription = <T>(
  channelName: string,
  config: {
    table: string;
    filter?: string;
    event?: "INSERT" | "UPDATE" | "DELETE" | "*";
  },
  callback: (payload: T) => void
) => {
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    const channel = supabase
      .channel(channelName)
      .on(
        "postgres_changes",
        {
          event: config.event || "*",
          schema: "public",
          table: config.table,
          filter: config.filter,
        },
        (payload) => {
          callback(payload as T);
        }
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      supabase.removeChannel(channel);
    };
  }, [channelName, config.table, config.filter, config.event]);

  return channelRef.current;
};

/**
 * 订听特定记录的变化
 */
export const useSupabaseRecord = <T>(
  table: string,
  id: string | null,
  queryFn: () => Promise<T>
) => {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);

  // 获取初始数据
  useEffect(() => {
    if (!id) {
      setLoading(false);
      return;
    }
    queryFn().then(setData).finally(() => setLoading(false));
  }, [id, queryFn]);

  // 实时订阅
  useSupabaseSubscription(
    `${table}:${id}`,
    {
      table,
      filter: `id=eq.${id}`,
    },
    (payload: any) => {
      if (payload.eventType === "UPDATE") {
        setData(payload.new);
      } else if (payload.eventType === "DELETE") {
        setData(null);
      } else if (payload.eventType === "INSERT") {
        setData(payload.new);
      }
    }
  );

  return { data, loading };
};

// ============================================================
// 存储相关 Hooks
// ============================================================

/**
 * 文件上传 Hook
 */
export const useSupabaseUpload = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [progress, setProgress] = useState(0);

  const upload = useCallback(
    async (bucket: string, path: string, file: File, options?: {
      upsert?: boolean;
      cacheControl?: string;
    }) => {
      setLoading(true);
      setError(null);
      setProgress(0);

      try {
        const { data, error } = await supabase.storage
          .from(bucket)
          .upload(path, file, {
            upsert: options?.upsert ?? false,
            cacheControl: options?.cacheControl ?? "3600",
          });

        if (error) throw error;

        setProgress(100);
        return data;
      } catch (err) {
        setError(err as Error);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { upload, loading, error, progress };
};

/**
 * 获取公共 URL Hook
 */
export const useSupabasePublicUrl = () => {
  const getPublicUrl = useCallback((bucket: string, path: string) => {
    const { data } = supabase.storage
      .from(bucket)
      .getPublicUrl(path);

    return data.publicUrl;
  }, []);

  return { getPublicUrl };
};
