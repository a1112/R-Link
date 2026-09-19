/**
 * API React Hooks
 * 提供便捷的 React Hooks 来调用 API
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { pluginsApi, systemApi } from './index';
import type {
  PluginInfo,
  PluginStatus,
  SystemInfo,
  SystemResources,
  SystemUptime,
  ProcessInfo,
} from './types';

// ========== 通用 Hook 类型 ==========

type ApiState<T> = {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
};

type ApiStateWithMutation<T, M = void> = ApiState<T> & {
  mutate: (...args: never[]) => Promise<M>;
};

// ========== 插件相关 Hooks ==========

/**
 * 获取所有插件列表
 */
export function usePlugins(): ApiState<Array<PluginInfo & { status?: PluginStatus }>> {
  const [state, setState] = useState<{
    data: Array<PluginInfo & { status?: PluginStatus }> | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await pluginsApi.listWithStatus();
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { ...state, refetch: fetch };
}

/**
 * 获取单个插件信息
 */
export function usePlugin(name: string): ApiState<PluginInfo> {
  const [state, setState] = useState<{
    data: PluginInfo | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    if (!name) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await pluginsApi.get(name);
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, [name]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { ...state, refetch: fetch };
}

/**
 * 获取插件状态（支持轮询）
 */
export function usePluginStatus(name: string, pollInterval: number = 5000): ApiState<PluginStatus> {
  const [state, setState] = useState<{
    data: PluginStatus | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    if (!name) return;

    try {
      const data = await pluginsApi.getStatus(name);
      setState((prev) => ({ ...prev, data, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, [name]);

  useEffect(() => {
    fetch();

    if (pollInterval > 0) {
      const interval = setInterval(fetch, pollInterval);
      return () => clearInterval(interval);
    }
  }, [fetch, pollInterval]);

  return { ...state, refetch: fetch };
}

/**
 * 插件操作 Hook
 */
export function usePluginActions() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const start = useCallback(async (name: string, config?: Record<string, unknown>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await pluginsApi.start(name, config);
      setLoading(false);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to start plugin');
      setError(error);
      setLoading(false);
      throw error;
    }
  }, []);

  const stop = useCallback(async (name: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await pluginsApi.stop(name);
      setLoading(false);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to stop plugin');
      setError(error);
      setLoading(false);
      throw error;
    }
  }, []);

  const restart = useCallback(async (name: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await pluginsApi.restart(name);
      setLoading(false);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to restart plugin');
      setError(error);
      setLoading(false);
      throw error;
    }
  }, []);

  return { start, stop, restart, loading, error };
}

// ========== 系统相关 Hooks ==========

/**
 * 获取系统信息
 */
export function useSystemInfo(): ApiState<SystemInfo> {
  const [state, setState] = useState<{
    data: SystemInfo | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await systemApi.getInfo();
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { ...state, refetch: fetch };
}

/**
 * 获取系统资源使用情况（支持轮询）
 */
export function useSystemResources(pollInterval: number = 5000): ApiState<SystemResources> {
  const [state, setState] = useState<{
    data: SystemResources | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    try {
      const data = await systemApi.getResources();
      setState((prev) => ({ ...prev, data, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, []);

  useEffect(() => {
    fetch();

    if (pollInterval > 0) {
      const interval = setInterval(fetch, pollInterval);
      return () => clearInterval(interval);
    }
  }, [fetch, pollInterval]);

  return { ...state, refetch: fetch };
}

/**
 * 获取系统进程列表
 */
export function useSystemProcesses(refreshInterval: number = 10000): ApiState<ProcessInfo[]> {
  const [state, setState] = useState<{
    data: ProcessInfo[] | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    try {
      const data = await systemApi.getProcesses();
      setState((prev) => ({ ...prev, data, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, []);

  useEffect(() => {
    fetch();

    if (refreshInterval > 0) {
      const interval = setInterval(fetch, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetch, refreshInterval]);

  return { ...state, refetch: fetch };
}

/**
 * 获取系统运行时间（支持轮询）
 */
export function useSystemUptime(pollInterval: number = 60000): ApiState<SystemUptime> {
  const [state, setState] = useState<{
    data: SystemUptime | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    try {
      const data = await systemApi.getUptime();
      setState((prev) => ({ ...prev, data, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, []);

  useEffect(() => {
    fetch();

    if (pollInterval > 0) {
      const interval = setInterval(fetch, pollInterval);
      return () => clearInterval(interval);
    }
  }, [fetch, pollInterval]);

  return { ...state, refetch: fetch };
}

/**
 * 获取系统概览（组合信息）
 */
export function useSystemOverview(pollInterval: number = 5000): ApiState<
  SystemInfo & { resources: SystemResources; uptime: SystemUptime }
> {
  const [state, setState] = useState<{
    data: (SystemInfo & { resources: SystemResources; uptime: SystemUptime }) | null;
    loading: boolean;
    error: Error | null;
  }>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(async () => {
    try {
      const data = await systemApi.getOverview();
      setState((prev) => ({ ...prev, data, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        data: prev.data,
        loading: false,
        error: err instanceof Error ? err : new Error('Unknown error'),
      }));
    }
  }, []);

  useEffect(() => {
    fetch();

    if (pollInterval > 0) {
      const interval = setInterval(fetch, pollInterval);
      return () => clearInterval(interval);
    }
  }, [fetch, pollInterval]);

  return { ...state, refetch: fetch };
}
