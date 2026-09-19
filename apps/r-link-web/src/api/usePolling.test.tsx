import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { usePolling } from './usePolling';
afterEach(() => { cleanup(); vi.useRealTimers(); });

it('does not overlap slow requests and cancels the active request on unmount', async () => {
  vi.useFakeTimers();
  let finish!: (value: number) => void;
  let signal!: AbortSignal;
  const load = vi.fn((current: AbortSignal) => { signal = current; return new Promise<number>(resolve => { finish = resolve; }); });
  const { result, unmount } = renderHook(() => usePolling(load, 1000));
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(load).toHaveBeenCalledTimes(1);
  await act(async () => { finish(12); });
  expect(result.current.data).toBe(12);
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(load).toHaveBeenCalledTimes(2);
  unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => { finish(99); await vi.advanceTimersByTimeAsync(5000); });
  expect(load).toHaveBeenCalledTimes(2);
});

it('discards an old target response and clears stale values after a failure', async () => {
  let finishOld!: (value: string) => void;
  const old = vi.fn(() => new Promise<string>(resolve => { finishOld = resolve; }));
  const current = vi.fn().mockResolvedValueOnce('current').mockRejectedValueOnce(new Error('offline'));
  const { result, rerender } = renderHook(({ loader }) => usePolling(loader), { initialProps: { loader: old } });
  await act(async () => { rerender({ loader: current }); });
  await act(async () => { finishOld('stale'); });
  expect(result.current.data).toBe('current');
  await act(async () => { await result.current.refetch(); });
  expect(result.current.data).toBeNull();
  expect(result.current.error?.message).toBe('offline');
});
