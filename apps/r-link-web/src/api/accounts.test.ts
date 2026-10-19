import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { accountsApi, clearDesktopAuthDiagnostics, getDesktopAuthDiagnostics } from './accounts';
import { resetAccount } from './account-access';

beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); resetAccount(); clearDesktopAuthDiagnostics();
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
