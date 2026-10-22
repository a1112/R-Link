import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { accountsApi } from './accounts';
import { resetAccount } from './account-access';
import { setServiceUrl } from './service-url';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
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
