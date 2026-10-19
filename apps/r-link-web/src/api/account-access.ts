import { API_CONFIG } from './config';

export type AccountRole = 'pending' | 'viewer' | 'operator' | 'admin';
export type AuthConfig = { mode: 'local' | 'service' | 'oidc'; login_enabled: boolean; desktop_login_enabled: boolean };
export type AccountUser = { id: string; issuer: string; subject: string; display_name: string; email: string | null; role: AccountRole; disabled: boolean; created_at?: string | number; last_login?: string | number };
export type AccountSession = { authenticated: boolean; mode: AuthConfig['mode']; user: AccountUser | null; csrf_token: string | null; expires_at: number | null; session_context?: string | null };
export type AccountState = { status: 'loading' | 'ready' | 'error'; config: AuthConfig | null; session: AccountSession | null; error: string; revision: number };

let state: AccountState = { status: 'loading', config: null, session: null, error: '', revision: 0 };
let desktopToken = '';
let configuredBase = '';
let requestRevision = 0;
const subscribers = new Set<() => void>();
const requests = new Set<AbortController>();

export function serviceBase(): string { return new URL(`${API_CONFIG.baseURL || ''}/`, window.location.href).toString().replace(/\/$/, ''); }
export function serviceEndpoint(path: string): string { return `${serviceBase()}${path}`; }
export const getAccountState = () => state;
export const accountRequestEpoch = () => requestRevision;
export function subscribeAccount(callback: () => void) { subscribers.add(callback); return () => { subscribers.delete(callback); }; }
const fingerprint = (value: AccountState) => `${value.config?.mode}:${value.session?.user?.id}:${value.session?.user?.role}:${value.session?.user?.disabled}:${value.session?.authenticated}:${value.session?.session_context ?? value.session?.csrf_token}`;
function stopRequests() { requestRevision++; requests.forEach(controller => controller.abort()); requests.clear(); }

export function updateAccount(next: Omit<AccountState, 'revision'>) {
  const changed = configuredBase !== serviceBase() || fingerprint(state) !== fingerprint({ ...next, revision: 0 });
  if (changed) stopRequests();
  configuredBase = serviceBase();
  state = { ...next, revision: state.revision + (changed ? 1 : 0) };
  subscribers.forEach(callback => callback());
}

export function resetAccount() {
  desktopToken = '';
  stopRequests();
  configuredBase = serviceBase();
  state = { status: 'loading', config: null, session: null, error: '', revision: state.revision + 1 };
  subscribers.forEach(callback => callback());
}

export function expireAccount() {
  desktopToken = '';
  updateAccount({ status: 'ready', config: state.config, session: { authenticated: false, mode: 'oidc', user: null, csrf_token: null, expires_at: null }, error: '' });
}

export function setDesktopSessionToken(token: string) { desktopToken = token; configuredBase = serviceBase(); }
export function requestAccountAccess() {
  if (configuredBase !== serviceBase()) return { mode: null, token: '', csrf: '', context: '', session: null, ready: false };
  return { mode: state.config?.mode, token: desktopToken, csrf: state.session?.csrf_token || '', context: state.session?.session_context || '', session: state.session, ready: state.status === 'ready' };
}

/** Identity changes cancel requests, including writes started by an old page. */
export function trackAccountRequest(signal?: AbortSignal | null) {
  const controller = new AbortController();
  const revision = requestRevision;
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once: true });
  requests.add(controller);
  return {
    signal: controller.signal,
    isCurrent: () => revision === requestRevision && !controller.signal.aborted,
    done: () => { requests.delete(controller); signal?.removeEventListener('abort', abort); },
  };
}

export function canOperate(state: AccountState) {
  if (state.status !== 'ready') return false;
  if (state.config?.mode !== 'oidc') return true;
  const user = state.session?.user;
  return !!state.session?.authenticated && !!user && !user.disabled && (user.role === 'operator' || user.role === 'admin');
}
export function isAccountAdmin(state: AccountState) { return state.config?.mode === 'oidc' && state.session?.authenticated && state.session.user?.role === 'admin' && !state.session.user.disabled; }

/** Keep legacy layouts, and isolate account annotations without deleting them. */
export function topologyAccountScope(base: string): string {
  if (state.config?.mode !== 'oidc') return base;
  const user = state.session?.authenticated ? state.session.user?.id : null;
  return `${serviceBase()}:account:${user ? encodeURIComponent(user) : 'anonymous'}`;
}
