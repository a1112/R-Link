import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
const config = vi.hoisted(() => ({ baseURL: 'https://api.example.test', timeout: 1000 }));
vi.mock('./config', () => ({ API_CONFIG: config }));
import { HttpClient } from './client';
import { accountsApi } from './accounts';
import { resetAccount, updateAccount } from './account-access';
import { rfileApi } from './rfile';
import { servicesApi } from './services';
import { storageApi } from './storage';
import { usePolling } from './usePolling';

const releases: (() => void)[] = [];
beforeEach(() => {
  resetAccount();
  updateAccount({ status: 'ready', config: { mode: 'service', login_enabled: false, desktop_login_enabled: false }, session: null, error: '' });
  // No test may fall through to the real network.
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Unexpected synthetic request')));
});
afterEach(async () => {
  cleanup();
  await act(async () => { releases.splice(0).forEach(release => release()); });
  resetAccount();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

/** Headers arrive immediately; the body stays open until completion or transport abort. */
function delayedBody(content = '{"value":"current"}') {
  let sink!: ReadableStreamDefaultController<Uint8Array>;
  let signal!: AbortSignal;
  let ended = false;
  let reading!: () => void;
  const started = new Promise<void>(resolve => { reading = resolve; });
  const stream = new ReadableStream<Uint8Array>({ start(controller) { sink = controller; } });
  const response = new Response(stream, { headers: { 'Content-Type': 'application/json' } });
  const json = response.json.bind(response);
  const blob = response.blob.bind(response);
  vi.spyOn(response, 'json').mockImplementation(() => { reading(); return json(); });
  vi.spyOn(response, 'blob').mockImplementation(() => { reading(); return blob(); });
  const abort = () => {
    if (ended) return;
    ended = true;
    sink.error(new DOMException('Synthetic transport cancelled', 'AbortError'));
  };
  vi.mocked(fetch).mockImplementation(async (_input, init) => {
    signal = init!.signal!;
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
    return response;
  });
  const finish = () => {
    signal?.removeEventListener('abort', abort);
    if (ended) return;
    ended = true;
    sink.enqueue(new TextEncoder().encode(content));
    sink.close();
  };
  releases.push(finish);
  return { started, finish, response, get signal() { return signal; } };
}

// Attach rejection handling before an abort, including when a baseline assertion fails.
function outcome<T>(pending: Promise<T>) {
  return pending.then(value => ({ value, error: null }), error => ({ value: null, error }));
}

it('cancels JSON consumption when the caller aborts after headers', async () => {
  const body = delayedBody();
  const caller = new AbortController();
  const result = outcome(new HttpClient().get('/api/example', { signal: caller.signal }));
  await body.started;
  caller.abort();
  expect(body.signal.aborted).toBe(true);
  expect((await result).error).toMatchObject({ name: 'AbortError' });
});

it('keeps the HTTP timeout active while reading JSON', async () => {
  vi.useFakeTimers();
  const body = delayedBody();
  const result = outcome(new HttpClient().get('/api/example'));
  await body.started;
  await vi.advanceTimersByTimeAsync(1000);
  expect(body.signal.aborted).toBe(true);
  expect((await result).error).toMatchObject({ message: '请求超时: 1000ms' });
  expect(vi.getTimerCount()).toBe(0);
});

it('cancels a JSON body on account change without calling it a timeout', async () => {
  const body = delayedBody();
  const result = outcome(new HttpClient().get('/api/devices'));
  await body.started;
  resetAccount();
  expect(body.signal.aborted).toBe(true);
  expect((await result).error).toMatchObject({ message: '账户或服务已更改，已忽略旧响应' });
});

it('lets the production polling hook cancel an active body on unmount', async () => {
  const body = delayedBody();
  const load = (signal: AbortSignal) => new HttpClient().get('/api/example', { signal });
  const view = renderHook(() => usePolling(load, 5000));
  await body.started;
  view.unmount();
  expect(body.signal.aborted).toBe(true);
  expect(fetch).toHaveBeenCalledOnce();
});

const cancellableDownloads = [
  ['shared storage', (signal: AbortSignal) => storageApi.download('fixture.txt', signal)],
  ['R-File bridge', (signal: AbortSignal) => rfileApi.download('fixture.txt', signal)],
] as const;

it.each(cancellableDownloads)('cancels a %s Blob body after headers', async (_name, download) => {
  const body = delayedBody('fixture bytes');
  const caller = new AbortController();
  const result = outcome(download(caller.signal));
  await body.started;
  caller.abort();
  expect(body.signal.aborted).toBe(true);
  expect((await result).error).toMatchObject({ name: 'AbortError' });
});

it.each(cancellableDownloads)('enforces the %s transfer deadline through Blob consumption', async (_name, download) => {
  vi.useFakeTimers();
  const body = delayedBody('fixture bytes');
  const result = outcome(download(new AbortController().signal));
  await body.started;
  await vi.advanceTimersByTimeAsync(120000);
  expect(body.signal.aborted).toBe(true);
  expect((await result).error).toMatchObject({ name: 'AbortError' });
  expect(vi.getTimerCount()).toBe(0);
});

const downloads = [
  ...cancellableDownloads.map(([name, download]) => [name, () => download(new AbortController().signal)] as const),
  ['managed download', () => servicesApi.downloadFile('synthetic-download')],
] as const;

it.each(downloads)('cancels a %s body when the account changes', async (_name, download) => {
  const body = delayedBody('fixture bytes');
  const result = outcome(download());
  await body.started;
  resetAccount();
  expect(body.signal.aborted).toBe(true);
  expect((await result).error).toMatchObject({ name: 'AbortError' });
});

it('keeps the account user-list body cancellable after headers', async () => {
  const body = delayedBody('{"users":[]}');
  const caller = new AbortController();
  const result = outcome(accountsApi.users(caller.signal));
  await body.started;
  caller.abort();
  expect(body.signal.aborted).toBe(true);
  expect((await result).error).toMatchObject({ name: 'AbortError' });
});

it('releases cancellation ownership and timers after a successful body', async () => {
  vi.useFakeTimers();
  const body = delayedBody();
  const caller = new AbortController();
  const result = new HttpClient().get('/api/example', { signal: caller.signal });
  await body.started;
  body.finish();
  expect(await result).toEqual({ value: 'current' });
  expect(vi.getTimerCount()).toBe(0);
  caller.abort();
  resetAccount();
  expect(body.signal.aborted).toBe(false);
});

it('releases ownership when body parsing fails', async () => {
  const body = delayedBody('invalid JSON');
  const caller = new AbortController();
  const result = outcome(new HttpClient().get('/api/example', { signal: caller.signal }));
  await body.started;
  body.finish();
  expect((await result).error).toMatchObject({ name: 'SyntaxError' });
  caller.abort();
  resetAccount();
  expect(body.signal.aborted).toBe(false);
});

it('discards an old Blob even if the body reader ignores transport abort', async () => {
  const body = delayedBody();
  let complete!: (blob: Blob) => void;
  let reading!: () => void;
  const started = new Promise<void>(resolve => { reading = resolve; });
  vi.mocked(body.response.blob).mockImplementation(() => {
    reading();
    return new Promise(resolve => { complete = resolve; });
  });
  const result = outcome(servicesApi.downloadFile('synthetic-download'));
  await started;
  resetAccount();
  complete(new Blob(['previous account bytes']));
  expect((await result).error).toMatchObject({ name: 'AbortError' });
});
