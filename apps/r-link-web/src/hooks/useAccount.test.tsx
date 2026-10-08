import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { accountsApi } from '../api/accounts';
import { requestAccountAccess, resetAccount, serviceEndpoint, type AccountUser } from '../api/account-access';
import { setServiceUrl } from '../api/service-url';
import { useAccount } from './useAccount';

vi.mock('../api/accounts', () => ({ accountsApi: { config: vi.fn(), session: vi.fn(), logout: vi.fn(), desktopStart: vi.fn(), desktopExchange: vi.fn() } }));
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
const user: AccountUser = { id: 'desktop-member', issuer: 'https://auth.example', subject: 'sub', display_name: 'Desktop Member', email: null, role: 'operator', disabled: false };

beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); resetAccount(); vi.clearAllMocks();
  vi.mocked(accountsApi.config).mockResolvedValue({ mode: 'oidc', login_enabled: true, desktop_login_enabled: true });
  vi.mocked(accountsApi.session).mockResolvedValue({ mode: 'oidc', authenticated: false, user: null, csrf_token: null, expires_at: null });
  vi.mocked(accountsApi.logout).mockResolvedValue(undefined);
  vi.mocked(invoke).mockResolvedValue(undefined);
  Object.defineProperty(window, '__TAURI_INTERNALS__', { configurable: true, value: {} });
});
afterEach(() => { cleanup(); resetAccount(); localStorage.clear(); sessionStorage.clear(); delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__; });

it('opens the current service login in the system browser and exchanges only an in-memory session', async () => {
  setServiceUrl('https://175.178.16.90/r-link');
  vi.mocked(accountsApi.desktopStart).mockResolvedValue({ login_url: serviceEndpoint('/api/auth/desktop/login?flow_id=flow-123'), flow_id: 'flow-123', poll_secret: 'poll-secret', expires_in: 300 });
  vi.mocked(accountsApi.desktopExchange).mockResolvedValue({ status: 200, value: { token: 'application-session', user } });
  const { result } = renderHook(useAccount);
  await waitFor(() => expect(result.current.account.status).toBe('ready'));
  vi.mocked(accountsApi.session).mockResolvedValue({ mode: 'oidc', authenticated: true, user, csrf_token: null, expires_at: null, session_context: 'desktop-context' });
  await act(async () => { await result.current.beginLogin(); });
  expect(invoke).toHaveBeenCalledWith('open_auth_login', { url: 'https://175.178.16.90/r-link/api/auth/desktop/login?flow_id=flow-123' });
  expect(accountsApi.desktopExchange).toHaveBeenCalledWith('flow-123', 'poll-secret', expect.any(AbortSignal));
  expect(requestAccountAccess().token).toBe('application-session');
  expect(sessionStorage.length).toBe(0);
  expect([...Array(localStorage.length)].map((_, i) => localStorage.getItem(localStorage.key(i)!))).not.toContain('application-session');
  await act(async () => { await result.current.logout(); });
  expect(requestAccountAccess().token).toBe(''); expect(result.current.account.session?.authenticated).toBe(false);
});

it.each(['https://evil.example/api/auth/desktop/login?flow_id=flow-123', 'https://175.178.16.90/other/api/auth/desktop/login?flow_id=flow-123', 'https://175.178.16.90/r-link/api/auth/desktop/login?flow_id=other', 'https://175.178.16.90/r-link/api/auth/desktop/login?flow_id=flow-123&redirect=https://evil.example'])('rejects an untrusted desktop login URL %s', async login_url => {
  setServiceUrl('https://175.178.16.90/r-link');
  vi.mocked(accountsApi.desktopStart).mockResolvedValue({ login_url, flow_id: 'flow-123', poll_secret: 'poll-secret', expires_in: 300 });
  const { result } = renderHook(useAccount); await waitFor(() => expect(result.current.account.status).toBe('ready'));
  await expect(result.current.beginLogin()).rejects.toThrow('桌面登录入口无效');
  expect(invoke).not.toHaveBeenCalled(); expect(accountsApi.desktopExchange).not.toHaveBeenCalled();
});

it('does not retry an old session after logout fails remotely', async () => {
  const { result } = renderHook(useAccount); await waitFor(() => expect(result.current.account.status).toBe('ready'));
  vi.mocked(accountsApi.logout).mockRejectedValue(new Error('服务不可达'));
  await act(async () => { await expect(result.current.logout()).rejects.toThrow('服务不可达'); });
  expect(result.current.account.session?.authenticated).toBe(false); expect(requestAccountAccess().token).toBe('');
  vi.mocked(accountsApi.session).mockResolvedValue({ mode: 'oidc', authenticated: true, user, csrf_token: 'old-csrf', expires_at: null, session_context: 'old-session' });
  await act(async () => { await result.current.refresh(); });
  expect(result.current.account.session?.authenticated).toBe(false);
});

it('cancels a delayed desktop start before it can open the system browser', async () => {
  setServiceUrl('https://175.178.16.90/r-link');
  let complete!: (flow: Awaited<ReturnType<typeof accountsApi.desktopStart>>) => void;
  vi.mocked(accountsApi.desktopStart).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  const { result } = renderHook(useAccount); await waitFor(() => expect(result.current.account.status).toBe('ready'));
  let login!: Promise<void>;
  act(() => { login = result.current.beginLogin(); });
  act(() => { result.current.cancelLogin(); });
  await act(async () => {
    complete({ login_url: serviceEndpoint('/api/auth/desktop/login?flow_id=flow-123'), flow_id: 'flow-123', poll_secret: 'poll-secret', expires_in: 300 });
    await login;
  });
  expect(invoke).not.toHaveBeenCalled(); expect(accountsApi.desktopExchange).not.toHaveBeenCalled();
  expect(requestAccountAccess().token).toBe('');
});
