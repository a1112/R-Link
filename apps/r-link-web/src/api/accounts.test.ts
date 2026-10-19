import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { accountsApi, clearDesktopAuthDiagnostics, getDesktopAuthDiagnostics } from './accounts';
import { resetAccount } from './account-access';
import { setServiceUrl } from './service-url';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));

describe('native desktop authentication', () => {
const flow = { login_url: 'https://175.178.16.90/r-link/api/auth/desktop/login?flow_id=abcdefghijklmnopqrstuv', flow_id: 'abcdefghijklmnopqrstuv', poll_secret: 'synthetic-poll-secret-abcdefghijklmnop', expires_in: 300 };
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); resetAccount(); vi.clearAllMocks();
  setServiceUrl('https://175.178.16.90/r-link');
  Object.defineProperty(window, '__TAURI_INTERNALS__', { configurable: true, value: {} });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Cross-site desktop request rejected' }), { status: 403 })));
});
afterEach(() => { vi.unstubAllGlobals(); delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__; resetAccount(); localStorage.clear(); sessionStorage.clear(); });

it('starts desktop login through native HTTPS instead of cross-site WebView fetch', async () => {
  vi.mocked(invoke).mockResolvedValue({ value: flow, status: 200 });
  expect(await accountsApi.desktopStart()).toEqual(flow);
  expect(invoke).toHaveBeenCalledWith('desktop_auth_request', { url: 'https://175.178.16.90/r-link/api/auth/desktop/start', operation: 'start' });
  expect(fetch).not.toHaveBeenCalled();
});

it('exchanges the poll secret only through the native fixed exchange route', async () => {
  vi.mocked(invoke).mockResolvedValue({ value: { pending: true }, status: 202 });
  expect(await accountsApi.desktopExchange(flow.flow_id, flow.poll_secret)).toEqual({ value: { pending: true }, status: 202 });
  expect(invoke).toHaveBeenCalledWith('desktop_auth_request', { url: 'https://175.178.16.90/r-link/api/auth/desktop/exchange', operation: 'exchange', flowId: flow.flow_id, pollSecret: flow.poll_secret });
  expect(fetch).not.toHaveBeenCalled();
});

it('does not fall back to browser fetch when native HTTPS fails', async () => {
  vi.mocked(invoke).mockRejectedValue(new Error('Native TLS verification failed'));
  await expect(accountsApi.desktopStart()).rejects.toThrow('Native TLS verification failed');
  expect(fetch).not.toHaveBeenCalled();
});

it('rejects an aborted native request without retaining its delayed response', async () => {
  let complete!: (value: unknown) => void;
  vi.mocked(invoke).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  const controller = new AbortController();
  const request = accountsApi.desktopStart(controller.signal);
  controller.abort();
  await expect(request).rejects.toMatchObject({ name: 'AbortError' });
  complete({ value: flow, status: 200 });
  expect(fetch).not.toHaveBeenCalled();
});

it('continues to discover a web session using same-origin cookies', async () => {
  delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
  setServiceUrl(window.location.origin);
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ authenticated: false, mode: 'oidc' }), { status: 200 }));
  expect(await accountsApi.session()).toMatchObject({ authenticated: false });
  expect(invoke).not.toHaveBeenCalled();
  expect(vi.mocked(fetch).mock.calls[0][1]).toMatchObject({ credentials: 'same-origin', redirect: 'error' });
});

});

describe('browser desktop authentication diagnostics', () => {
beforeEach(() => {
  delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
  localStorage.clear(); sessionStorage.clear(); resetAccount(); clearDesktopAuthDiagnostics();
  setServiceUrl(window.location.origin);
  vi.stubGlobal('fetch', vi.fn()); vi.spyOn(console, 'warn').mockImplementation(() => {}); vi.spyOn(console, 'info').mockImplementation(() => {});
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('identifies an exchange fetch failure without exposing flow proof, headers or raw errors', async () => {
  vi.mocked(fetch).mockRejectedValue(new TypeError('Load failed private-flow private-poll private-token'));
  await expect(accountsApi.desktopExchange('private-flow', 'private-poll')).rejects.toThrow('桌面登录交换请求未收到响应');
  const trace = getDesktopAuthDiagnostics()[0];
  expect(trace).toMatchObject({ stage: 'exchange', phase: 'fetch', endpoint_path: '/api/auth/desktop/exchange', method: 'POST', response_received: false, http_status: null, error_type: 'TypeError', caller_aborted: false });
  const output = JSON.stringify({ trace, console: vi.mocked(console.warn).mock.calls });
  expect(output).not.toMatch(/private-flow|private-poll|private-token|Authorization|Cookie|poll_secret|flow_id/);
});

it('normalizes a caller cancellation even when WebKit reports a generic Load failed', async () => {
  const controller = new AbortController(); controller.abort();
  vi.mocked(fetch).mockRejectedValue(new TypeError('Load failed'));
  await expect(accountsApi.desktopExchange('flow', 'proof', controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  expect(getDesktopAuthDiagnostics()[0].caller_aborted).toBe(true);
});

it('keeps a genuine HTTP rejection separate from a missing network response', async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json({ detail: 'Cross-site desktop request rejected' }, { status: 403 }));
  await expect(accountsApi.desktopStart()).rejects.toThrow('桌面登录启动被服务拒绝（HTTP 403）');
  expect(getDesktopAuthDiagnostics()[0]).toMatchObject({ stage: 'start', response_received: true, http_status: 403, error_type: null });
});

it('captures a failed response body separately without logging its content', async () => {
  const response = Response.json({ pending: true }, { status: 202 });
  vi.spyOn(response, 'json').mockRejectedValue(new TypeError('Load failed private-body-token'));
  vi.mocked(fetch).mockResolvedValue(response);
  await expect(accountsApi.desktopExchange('private-flow', 'private-poll')).rejects.toThrow('桌面登录交换响应读取失败（HTTP 202');
  expect(getDesktopAuthDiagnostics()[0]).toMatchObject({ phase: 'response_json', stage: 'exchange', http_status: 202, response_received: true, error_type: 'TypeError' });
  expect(JSON.stringify(vi.mocked(console.warn).mock.calls)).not.toMatch(/private-body-token|private-flow|private-poll/);
});

it('treats anonymous 202 as normal pending, preserves browser credential restrictions and bounds failures', async () => {
  vi.mocked(fetch).mockImplementation(async () => Response.json({ pending: true }, { status: 202 }));
  expect(await accountsApi.desktopExchange('flow', 'proof')).toEqual({ status: 202, value: { pending: true } });
  expect(getDesktopAuthDiagnostics()).toHaveLength(1);
  expect(getDesktopAuthDiagnostics()[0]).toMatchObject({ phase: 'response', http_status: 202 });
  for (let i = 0; i < 10; i++) await accountsApi.desktopExchange('flow', 'proof');
  expect(getDesktopAuthDiagnostics()).toHaveLength(1); expect(console.info).toHaveBeenCalledTimes(1);
  expect(vi.mocked(fetch).mock.calls[0][1]?.redirect).toBe('error');
  vi.mocked(fetch).mockRejectedValue(new TypeError('Load failed'));
  for (let i = 0; i < 10; i++) await accountsApi.desktopExchange('flow', 'proof').catch(() => undefined);
  expect(getDesktopAuthDiagnostics().filter(item => item.phase !== 'response')).toHaveLength(8); expect(console.warn).toHaveBeenCalledTimes(8);
});

});
