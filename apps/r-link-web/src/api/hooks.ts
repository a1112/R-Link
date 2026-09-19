import { useState, useCallback } from 'react';
import { pluginsApi, systemApi } from './index';
import { usePolling } from './usePolling';

export function usePlugins() {
  return usePolling(useCallback((signal: AbortSignal) => pluginsApi.listWithStatus(signal), []));
}
export function usePlugin(name: string) {
  return usePolling(useCallback((signal: AbortSignal) => name ? pluginsApi.get(name, signal) : Promise.resolve(null), [name]));
}
export function usePluginStatus(name: string, interval = 5000) {
  return usePolling(useCallback((signal: AbortSignal) => name ? pluginsApi.getStatus(name, signal) : Promise.resolve(null), [name]), interval);
}
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


export function useSystemInfo() {
  return usePolling(useCallback((signal: AbortSignal) => systemApi.getInfo(signal), []));
}
export function useSystemResources(interval = 5000) {
  return usePolling(useCallback((signal: AbortSignal) => systemApi.getResources(signal), []), interval);
}
export function useSystemProcesses(interval = 10000) {
  return usePolling(useCallback((signal: AbortSignal) => systemApi.getProcesses(signal), []), interval);
}
export function useSystemUptime(interval = 60000) {
  return usePolling(useCallback((signal: AbortSignal) => systemApi.getUptime(signal), []), interval);
}
export function useSystemOverview(interval = 5000) {
  return usePolling(useCallback((signal: AbortSignal) => systemApi.getOverview(signal), []), interval);
}
