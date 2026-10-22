import { requestAccountAccess, serviceEndpoint, type AccountRole, type AccountSession, type AccountUser, type AuthConfig } from './account-access';
import { authenticatedFetch } from './authenticated-fetch';
import { invoke } from '@tauri-apps/api/core';
import { isTauriRuntime } from '../utils/tauriWindow';

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
  const response = await fetch(url.toString(), { ...init, headers, credentials: !token && url.origin === window.location.origin ? 'same-origin' : 'omit', redirect: 'error' });
  const value = response.status === 204 ? undefined : await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof value?.detail === 'string' ? value.detail : `HTTP ${response.status}`);
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
