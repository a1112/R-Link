import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { authenticatedFetch } from './authenticated-fetch';
import { bridgeProxyApi as api, BridgeProxyError } from './bridgeproxy';
import { resetAccount, serviceEndpoint, updateAccount } from './account-access';
import { setServiceUrl } from './service-url';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
vi.mock('./authenticated-fetch', () => ({ authenticatedFetch: vi.fn() }));

const operationId = 'a'.repeat(64);
const revision = 'b'.repeat(64);
const envelope = (data: unknown, status = 200) => Response.json({ api_version: 'v1', data }, { status });

beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); sessionStorage.clear(); resetAccount();
  setServiceUrl('https://server.example/r-link');
  updateAccount({ status: 'ready', config: { mode: 'service', login_enabled: false, desktop_login_enabled: false }, session: null, error: '' });
});
afterEach(() => { vi.useRealTimers(); resetAccount(); localStorage.clear(); sessionStorage.clear(); });

it('sends local business requests through native code without renderer credentials or HTTP fallback', async () => {
  vi.mocked(invoke).mockResolvedValue({ status: 200, body: { api_version: 'v1', data: { running: true } } });
  expect(await api.request('local', { method: 'GET', path: '/v1/status' })).toEqual({ running: true });
  expect(invoke).toHaveBeenCalledWith('bridgeproxy_request', { request: {
    method: 'GET', path: '/v1/status', body: null, revision: null, idempotency_key: null,
  } });
  expect(authenticatedFetch).not.toHaveBeenCalled();
  vi.mocked(invoke).mockRejectedValueOnce(new Error('Core is unavailable'));
  await expect(api.request('local', { method: 'POST', path: '/v1/service/start' })).rejects.toThrow('Core is unavailable');
  expect(authenticatedFetch).not.toHaveBeenCalled();
});

it('uses the configured server facade and preserves revision, idempotency and JSON payload', async () => {
  vi.mocked(authenticatedFetch).mockResolvedValue(envelope({ operation_id: operationId, status: 'queued' }, 202));
  const body = { rules: [{ enabled: true, kind: 'domain', value: 'example.test', action: 'direct' }], final_action: 'block', apply: true };
  await api.request('server', { method: 'PUT', path: '/v1/rules', body, revision, idempotency_key: 'same-request-key' });
  expect(authenticatedFetch).toHaveBeenCalledTimes(1);
  const [url, init, options] = vi.mocked(authenticatedFetch).mock.calls[0];
  expect(url).toBe(serviceEndpoint('/api/bridgeproxy/v1/rules'));
  expect(init?.method).toBe('PUT'); expect(init?.body).toBe(JSON.stringify(body));
  expect(new Headers(init?.headers).get('If-Match')).toBe(revision);
  expect(new Headers(init?.headers).get('Idempotency-Key')).toBe('same-request-key');
  expect(new Headers(init?.headers).has('Authorization')).toBe(false);
  expect(options).toEqual({ coreErrors: true }); expect(invoke).not.toHaveBeenCalled();
});

it('retains a Core credential rejection status and code without retrying a write', async () => {
  vi.mocked(authenticatedFetch).mockResolvedValue(Response.json({ api_version: 'v1', error: {
    status: 401, code: 'unauthorized', message: 'Core credential is no longer valid',
  } }, { status: 401 }));
  await expect(api.request('server', { method: 'POST', path: '/v1/service/start' })).rejects.toMatchObject({
    status: 401, code: 'unauthorized', message: 'Core credential is no longer valid',
  });
  expect(authenticatedFetch).toHaveBeenCalledTimes(1);
});

it('discards a late native response after the account epoch changes', async () => {
  let complete!: (value: unknown) => void;
  vi.mocked(invoke).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  const result = api.request('local', { method: 'GET', path: '/v1/pairings/control' });
  const rejected = expect(result).rejects.toMatchObject({ name: 'AbortError' });
  resetAccount();
  complete({ status: 200, body: { api_version: 'v1', data: { pending: [{ verification_code: '12345678' }] } } });
  await rejected;
});

it('does not return a delayed connect grant to a cancelled page', async () => {
  let complete!: (value: unknown) => void;
  vi.mocked(invoke).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  const controller = new AbortController();
  const result = api.connect('C:\\Core-data', true, controller.signal);
  const rejected = expect(result).rejects.toMatchObject({ name: 'AbortError' });
  controller.abort();
  complete({ configured: true, control_configured: true, target: 'local' });
  await rejected;
  expect(invoke).toHaveBeenCalledWith('bridgeproxy_connect', { dataDir: 'C:\\Core-data', allowControl: true });
});

it('polls an accepted operation and preserves asynchronous business error status and identity', async () => {
  vi.useFakeTimers();
  vi.mocked(authenticatedFetch).mockResolvedValueOnce(envelope({ operation_id: operationId, status: 'queued' }, 202))
    .mockResolvedValueOnce(envelope({ operation_id: operationId, status: 'failed', error: {
      status: 412, code: 'revision_mismatch', message: '配置已改变',
    } }));
  const result = api.command('server', { method: 'PATCH', path: '/v1/config', body: { name: 'changed' }, revision });
  const rejected = expect(result).rejects.toMatchObject({ status: 412, code: 'revision_mismatch', operationId });
  await vi.advanceTimersByTimeAsync(250); await rejected;
  expect(authenticatedFetch).toHaveBeenCalledTimes(2);
  expect(vi.mocked(authenticatedFetch).mock.calls[1][0]).toBe(serviceEndpoint('/api/bridgeproxy/v1/operations/' + operationId));
  expect(vi.mocked(authenticatedFetch).mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1);
});

it('returns dispatch success without pretending that the resulting tunnel is already ready', async () => {
  vi.useFakeTimers();
  vi.mocked(authenticatedFetch).mockResolvedValueOnce(envelope({ operation_id: operationId, status: 'queued' }, 202))
    .mockResolvedValueOnce(envelope({ operation_id: operationId, status: 'running' }))
    .mockResolvedValueOnce(envelope({ operation_id: operationId, status: 'succeeded', result: { queued: true, action: 'start' } }));
  const result = api.command('server', { method: 'POST', path: '/v1/service/start' });
  await vi.advanceTimersByTimeAsync(500);
  expect(await result).toEqual({ queued: true, action: 'start' });
  expect(authenticatedFetch).toHaveBeenCalledTimes(3);
});

it('cancels operation polling without resubmitting the accepted command', async () => {
  vi.useFakeTimers();
  vi.mocked(authenticatedFetch).mockResolvedValue(envelope({ operation_id: operationId, status: 'queued' }, 202));
  const controller = new AbortController();
  const result = api.command('server', { method: 'POST', path: '/v1/service/start' }, controller.signal);
  const rejected = expect(result).rejects.toMatchObject({ name: 'AbortError' });
  await vi.advanceTimersByTimeAsync(0); controller.abort(); await rejected;
  await vi.advanceTimersByTimeAsync(1000);
  expect(authenticatedFetch).toHaveBeenCalledTimes(1);
});

it('keeps the accepted operation ID when completion cannot be confirmed by the deadline', async () => {
  vi.useFakeTimers();
  vi.mocked(authenticatedFetch).mockImplementation(async (_input, init) => init?.method === 'POST'
    ? envelope({ operation_id: operationId, status: 'queued' }, 202)
    : envelope({ operation_id: operationId, status: 'running' }));
  const result = api.command('server', { method: 'POST', path: '/v1/service/restart' });
  const rejected = expect(result).rejects.toMatchObject({ code: 'operation_pending', status: 202, operationId });
  await vi.advanceTimersByTimeAsync(20500); await rejected;
  expect(vi.mocked(authenticatedFetch).mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
});

it('rejects an incompatible Core envelope before consuming it as a resource', async () => {
  vi.mocked(invoke).mockResolvedValue({ status: 200, body: { api_version: 'v2', data: { running: true } } });
  await expect(api.request('local', { method: 'GET', path: '/v1/status' })).rejects.toBeInstanceOf(BridgeProxyError);
});
