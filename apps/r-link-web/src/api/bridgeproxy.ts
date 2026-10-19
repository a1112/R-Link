import { invoke } from '@tauri-apps/api/core';
import { authenticatedFetch } from './authenticated-fetch';
import { serviceEndpoint, trackAccountRequest } from './account-access';

export type BridgeTarget = 'local' | 'server';
export type JsonObject = Record<string, unknown>;
export type BridgeAdapter = { configured: boolean; control_configured: boolean; supported?: boolean; platform?: string; credential_protection?: string; target: BridgeTarget; endpoint_scope: string; data_dir?: string };
export type BridgeRequest = { method: string; path: string; body?: unknown; revision?: string; idempotency_key?: string };
type Envelope = { api_version: string; data?: unknown; error?: { code?: string; message?: string; details?: unknown } };
type NativeResponse = { status: number; body: Envelope; etag?: string };
export class BridgeProxyError extends Error {
  constructor(message: string, readonly code: string, readonly status = 0, public operationId?: string) { super(message); }
}
export const object = (value: unknown): JsonObject => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : {};
export const records = (value: unknown): JsonObject[] => Array.isArray(value) ? value.map(object) : [];
export const text = (value: unknown, fallback = '—'): string => typeof value === 'string' || typeof value === 'number' ? String(value) : fallback;

function abort() { return new DOMException('已取消 Core 请求', 'AbortError'); }
const sleep = (signal: AbortSignal, milliseconds: number) => new Promise<void>((resolve, reject) => {
  const stop = () => { clearTimeout(timer); signal.removeEventListener('abort', stop); reject(abort()); };
  const timer = setTimeout(() => { signal.removeEventListener('abort', stop); resolve(); }, milliseconds);
  signal.addEventListener('abort', stop, { once: true }); if (signal.aborted) stop();
});

export const bridgeProxyApi = {
  async adapter(target: BridgeTarget, signal?: AbortSignal): Promise<BridgeAdapter> {
    if (target === 'local') return invoke<BridgeAdapter>('bridgeproxy_adapter_info');
    const response = await authenticatedFetch(serviceEndpoint('/api/bridgeproxy/v1/adapter'), { signal, redirect: 'error' });
    if (!response.ok) throw new BridgeProxyError('无法读取服务端 Core 接入配置', 'adapter_unavailable', response.status);
    const value = object(await response.json());
    return object(value.data ?? value) as unknown as BridgeAdapter;
  },
  async connect(dataDir: string, allowControl: boolean, signal?: AbortSignal): Promise<BridgeAdapter> {
    const tracked = trackAccountRequest(signal);
    try {
      if (!tracked.isCurrent()) throw abort();
      const result = await invoke<BridgeAdapter>('bridgeproxy_connect', { dataDir, allowControl });
      if (!tracked.isCurrent()) throw abort();
      return result;
    } finally { tracked.done(); }
  },
  disconnect: () => invoke<void>('bridgeproxy_disconnect'),
  async request<T = JsonObject>(target: BridgeTarget, request: BridgeRequest, signal?: AbortSignal): Promise<T> {
    const tracked = trackAccountRequest(signal);
    try {
      if (!tracked.isCurrent()) throw abort();
      let result: NativeResponse;
      if (target === 'local') {
        result = await invoke<NativeResponse>('bridgeproxy_request', { request: {
          method: request.method, path: request.path, body: request.body ?? null,
          revision: request.revision ?? null, idempotency_key: request.idempotency_key ?? null,
        } });
      } else {
        const headers = new Headers({ 'Accept': 'application/json' });
        if (request.revision) headers.set('If-Match', request.revision);
        if (request.idempotency_key) headers.set('Idempotency-Key', request.idempotency_key);
        if (request.method !== 'GET') headers.set('Content-Type', 'application/json');
        const response = await authenticatedFetch(serviceEndpoint(`/api/bridgeproxy${request.path}`), {
          method: request.method, headers, signal: tracked.signal, redirect: 'error',
          ...(request.method === 'GET' ? {} : { body: JSON.stringify(request.body ?? null) }),
        }, { coreErrors: true });
        result = { status: response.status, body: await response.json() as Envelope };
      }
      if (!tracked.isCurrent()) throw abort();
      if (result.body.api_version !== 'v1') throw new BridgeProxyError('Core API 响应版本不兼容', 'incompatible_api', result.status);
      if (result.status < 200 || result.status >= 300 || result.body.error) {
        throw new BridgeProxyError(result.body.error?.message || `Core 请求失败（HTTP ${result.status}）`, result.body.error?.code || 'core_request_failed', result.status);
      }
      return result.body.data as T;
    } finally { tracked.done(); }
  },
  async command(target: BridgeTarget, request: BridgeRequest, signal?: AbortSignal): Promise<JsonObject> {
    const tracked = trackAccountRequest(signal);
    try {
      const accepted = await this.request<JsonObject>(target, { ...request, idempotency_key: request.idempotency_key || crypto.randomUUID() }, tracked.signal);
      if (typeof accepted.operation_id !== 'string') return accepted;
      const deadline = Date.now() + 20000;
      while (Date.now() < deadline) {
        await sleep(tracked.signal, 250);
        const operation = await this.request<JsonObject>(target, { method: 'GET', path: `/v1/operations/${accepted.operation_id}` }, tracked.signal);
        if (operation.status === 'failed') {
          const error = object(operation.error);
          throw new BridgeProxyError(text(error.message, 'Core 操作未完成'), text(error.code, 'operation_failed'), Number(error.status) || 0, accepted.operation_id);
        }
        if (operation.status === 'succeeded') return object(operation.result);
      }
      throw new BridgeProxyError('操作已受理，尚未确认完成。请刷新任务列表，勿重复提交。', 'operation_pending', 202, accepted.operation_id);
    } finally { tracked.done(); }
  },
};
