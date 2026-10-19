import { requestAccountAccess, serviceEndpoint, type AccountRole, type AccountSession, type AccountUser, type AuthConfig } from './account-access';
import { authenticatedFetch } from './authenticated-fetch';
import { invoke } from '@tauri-apps/api/core';
import { isTauriRuntime } from '../utils/tauriWindow';

type DesktopStage = 'start' | 'exchange';
export class DesktopAuthNetworkError extends Error {
  readonly name = 'DesktopAuthNetworkError';
  constructor(message: string, readonly phase: 'fetch' | 'response_json') { super(message); }
}
export type DesktopAuthDiagnostic = {
  recorded_at: string;
  phase: 'fetch' | 'response_json' | 'http_rejection' | 'response';
  stage: DesktopStage; method: 'POST'; endpoint_path: string; service_origin: string;
  page_origin: string; page_protocol: string; visibility: DocumentVisibilityState;
  elapsed_ms: number; response_received: boolean; http_status: number | null;
  error_type: string | null; caller_aborted: boolean;
};
const diagnostics: DesktopAuthDiagnostic[] = [];
const diagnosticLimit = 8;
let failureDiagnostics = 0;
const successfulDiagnostics = new Set<string>();
export const getDesktopAuthDiagnostics = () => diagnostics.map(item => ({ ...item }));
export function clearDesktopAuthDiagnostics() { diagnostics.length = 0; failureDiagnostics = 0; successfulDiagnostics.clear(); }

function desktopStage(path: string): DesktopStage | null {
  return path === '/api/auth/desktop/start' ? 'start' : path === '/api/auth/desktop/exchange' ? 'exchange' : null;
}
function recordDesktopDiagnostic(stage: DesktopStage, phase: DesktopAuthDiagnostic['phase'], url: URL, init: RequestInit, started: number, status: number | null, error?: unknown) {
  const name = error && typeof error === 'object' && 'name' in error ? String(error.name) : '';
  const allowedNames = ['TypeError', 'Error', 'AbortError', 'NetworkError', 'SecurityError', 'TimeoutError', 'SyntaxError'];
  const diagnostic: DesktopAuthDiagnostic = {
    recorded_at: new Date().toISOString(),
    stage, phase, method: 'POST', endpoint_path: url.pathname, service_origin: url.origin,
    page_origin: window.location.origin, page_protocol: window.location.protocol, visibility: document.visibilityState,
    elapsed_ms: Math.max(0, Math.round(performance.now() - started)), response_received: status !== null,
    http_status: status, error_type: error === undefined ? null : allowedNames.includes(name) ? name : 'unknown',
    caller_aborted: init.signal?.aborted === true,
  };
  // Never record query strings, flow proof, headers, bodies or raw exception messages.
  const successKey = `${stage}:${status}`;
  const capture = phase === 'response'
    ? successfulDiagnostics.size < 3 && !successfulDiagnostics.has(successKey)
    : failureDiagnostics < diagnosticLimit;
  if (capture) {
    diagnostics.push(diagnostic);
    if (phase === 'response') { successfulDiagnostics.add(successKey); console.info('[R-Link desktop-auth request]', diagnostic); }
    else { failureDiagnostics++; console.warn('[R-Link desktop-auth request]', diagnostic); }
  }
  return diagnostic;
}

/** Desktop flow secrets stay in native POST bodies; browser session discovery keeps its cookie rules. */
function desktopRequest<T>(operation: 'start' | 'exchange', flowId?: string, pollSecret?: string, signal?: AbortSignal): Promise<{ value: T; status: number }> {
  const path = `/api/auth/desktop/${operation}`;
  if (!isTauriRuntime()) return authRequest<T>(path, { method: 'POST', body: operation === 'start' ? '{}' : JSON.stringify({ flow_id: flowId, poll_secret: pollSecret }), signal });
  if (signal?.aborted) return Promise.reject(new DOMException('已取消登录', 'AbortError'));
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('已取消登录', 'AbortError'));
    signal?.addEventListener('abort', abort, { once: true });
    const args = { url: serviceEndpoint(path), operation, ...(operation === 'exchange' ? { flowId, pollSecret } : {}) };
    invoke<{ value: T; status: number }>('desktop_auth_request', args).then(response => {
      if (!signal?.aborted) resolve(response);
    }, reject).finally(() => signal?.removeEventListener('abort', abort));
  });
}

/** Session discovery never sends a legacy service key or cross-origin Cookies. */
async function authRequest<T>(path: string, init: RequestInit = {}): Promise<{ value: T; status: number }> {
  const url = new URL(serviceEndpoint(path));
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  headers.delete('Authorization');
  const { token, csrf, context } = requestAccountAccess();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (csrf && !['GET', 'HEAD'].includes((init.method || 'GET').toUpperCase())) headers.set('X-R-Link-CSRF', csrf);
  if (context && !['GET', 'HEAD'].includes((init.method || 'GET').toUpperCase())) headers.set('X-R-Link-Session-Context', context);
  if (init.body) headers.set('Content-Type', 'application/json');
  const stage = desktopStage(path);
  const started = performance.now();
  let response: Response;
  try {
    response = await fetch(url.toString(), { ...init, headers, credentials: !token && url.origin === window.location.origin ? 'same-origin' : 'omit', redirect: 'error' });
  } catch (error) {
    if (!stage) throw error;
    const diagnostic = recordDesktopDiagnostic(stage, 'fetch', url, init, started, null, error);
    if (diagnostic.caller_aborted) throw new DOMException('已取消桌面登录请求', 'AbortError');
    const label = stage === 'start' ? '启动' : '交换';
    throw new DesktopAuthNetworkError(`桌面登录${label}请求未收到响应（${diagnostic.endpoint_path}；${diagnostic.error_type}；页面${diagnostic.visibility}；${diagnostic.elapsed_ms} ms）。请检查网络或系统代理；尚未完成账户登录。`, 'fetch');
  }
  let value;
  try { value = response.status === 204 ? undefined : await response.json(); }
  catch (error) {
    if (!stage) value = null;
    else {
      const diagnostic = recordDesktopDiagnostic(stage, 'response_json', url, init, started, response.status, error);
      if (diagnostic.caller_aborted) throw new DOMException('已取消桌面登录请求', 'AbortError');
      throw new DesktopAuthNetworkError(`桌面登录${stage === 'start' ? '启动' : '交换'}响应读取失败（HTTP ${response.status}；${diagnostic.error_type}；页面${diagnostic.visibility}；${diagnostic.elapsed_ms} ms）。尚未完成账户登录。`, 'response_json');
    }
  }
  if (!response.ok) {
    const detail = typeof value?.detail === 'string' ? value.detail : `HTTP ${response.status}`;
    if (stage) {
      recordDesktopDiagnostic(stage, 'http_rejection', url, init, started, response.status);
      throw new Error(`桌面登录${stage === 'start' ? '启动' : '交换'}被服务拒绝（HTTP ${response.status}）：${detail}`);
    }
    throw new Error(detail);
  }
  if (stage && (response.status === 200 || response.status === 202)) recordDesktopDiagnostic(stage, 'response', url, init, started, response.status);
  return { value, status: response.status };
}

export const accountsApi = {
  config: async (signal?: AbortSignal) => {
    const { value } = await authRequest<AuthConfig>('/api/auth/config', { signal });
    if (!value || !['local', 'service', 'oidc'].includes(value.mode)) throw new Error('服务未返回有效的账户配置');
    return value;
  },
  session: async (signal?: AbortSignal) => (await authRequest<AccountSession>('/api/auth/session', { signal })).value,
  logout: async () => { await authRequest('/api/auth/logout', { method: 'POST' }); },
  desktopStart: async (signal?: AbortSignal) => (await desktopRequest<{ login_url: string; flow_id: string; poll_secret: string; expires_in: number }>('start', undefined, undefined, signal)).value,
  desktopExchange: (flow_id: string, poll_secret: string, signal?: AbortSignal) => desktopRequest<{ pending?: boolean; token?: string; expires_at?: number; user?: AccountUser }>('exchange', flow_id, poll_secret, signal),
  users: async (signal?: AbortSignal) => {
    const response = await authenticatedFetch(serviceEndpoint('/api/auth/users'), { signal });
    return (await response.json() as { users: AccountUser[] }).users;
  },
  updateUser: async (id: string, changes: { role?: AccountRole; disabled?: boolean }, signal?: AbortSignal) => {
    const response = await authenticatedFetch(serviceEndpoint(`/api/auth/users/${encodeURIComponent(id)}`), { method: 'PATCH', body: JSON.stringify(changes), headers: { 'Content-Type': 'application/json' }, signal });
    return await response.json() as AccountUser;
  },
};
