import { useCallback, useEffect, useRef, useState } from 'react';

/** At most one request at a time; stale/unmounted responses cannot overwrite current state. */
export function usePolling<T>(load: (signal: AbortSignal) => Promise<T>, interval = 0) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: Error | null }>({ data: null, loading: true, error: null });
  const runner = useRef<() => Promise<void>>(() => Promise.resolve());
  useEffect(() => {
    let active = true;
    let pending: Promise<void> | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    setState({ data: null, loading: true, error: null });
    const run = (): Promise<void> => {
      if (!active) return Promise.resolve();
      if (pending) return pending;
      clearTimeout(timer);
      controller = new AbortController();
      pending = (async () => {
        try {
          const data = await load(controller!.signal);
          if (active) setState({ data, loading: false, error: null });
        } catch (error) {
          if (active) setState({ data: null, loading: false, error: error instanceof Error ? error : new Error(String(error)) });
        } finally {
          pending = null;
          if (active && interval > 0) timer = setTimeout(() => void run(), interval);
        }
      })();
      return pending;
    };
    runner.current = run;
    void run();
    return () => { active = false; clearTimeout(timer); controller?.abort(); };
  }, [load, interval]);
  const refetch = useCallback(() => runner.current(), []);
  return { ...state, refetch };
}
