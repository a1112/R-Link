import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
const config = vi.hoisted(() => ({ baseURL: 'https://api.example.test' }));
vi.mock('./config', () => ({ API_CONFIG: config }));
import { authenticatedFetch } from './authenticated-fetch';
import { getServiceKey, setServiceKey } from './service-access';
import { getAccountState, resetAccount, setDesktopSessionToken, updateAccount, type AccountUser } from './account-access';
const legacy = () => updateAccount({ status: 'ready', config: { mode: 'service', login_enabled: false, desktop_login_enabled: false }, session: null, error: '' });

describe('service API requests', () => {
  beforeEach(() => {
    sessionStorage.clear();
    config.baseURL = 'https://api.example.test';
    resetAccount(); legacy();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));
  });
  afterEach(() => vi.unstubAllGlobals());
  it('works without a cloud session or access key', async () => {
    await authenticatedFetch('https://api.example.test/api/plugins/', { headers: { Authorization: 'stale' } });
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(new Headers(init?.headers).has('Authorization')).toBe(false);
    expect(init?.credentials).toBe('omit');
    expect(init?.redirect).toBe('error');
  });
  it('uses the current optional service key and preserves caller headers', async () => {
    setServiceKey('first');
    await authenticatedFetch('https://api.example.test/api/plugins/', { headers: { 'X-Trace': '1' } });
    setServiceKey('second');
    await authenticatedFetch('https://api.example.test/api/system/info');
    const calls = vi.mocked(fetch).mock.calls;
    expect(new Headers(calls[0][1]?.headers).get('Authorization')).toBe('Bearer first');
    expect(new Headers(calls[0][1]?.headers).get('X-Trace')).toBe('1');
    expect(new Headers(calls[1][1]?.headers).get('Authorization')).toBe('Bearer second');
  });
  it('rejects unrelated origins before sending credentials', async () => {
    setServiceKey('private');
    await expect(authenticatedFetch('https://elsewhere.example/api/plugins/')).rejects.toThrow('未配置');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('keeps service keys inside the configured application path', async () => {
    config.baseURL = 'https://api.example.test/r-link'; legacy(); setServiceKey('private-service-key');
    await expect(authenticatedFetch('https://api.example.test/r-auth/api/session')).rejects.toThrow('服务路径之外');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('does not reuse keys across API origins and supports clearing', () => {
    setServiceKey('private');
    config.baseURL = 'https://different.example';
    expect(getServiceKey()).toBe('');
    config.baseURL = 'https://api.example.test';
    expect(getServiceKey()).toBe('private');
    setServiceKey('');
    expect(getServiceKey()).toBe('');
  });
  it('surfaces service denials', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('{"detail":"Service access key required"}', { status: 401 }));
    await expect(authenticatedFetch('https://api.example.test/api/console/start', { method: 'POST' })).rejects.toThrow('Service access key required');
  });
  it('never forwards a stored service key while discovering authentication', async () => {
    setServiceKey('admin-service-secret'); resetAccount();
    await expect(authenticatedFetch('https://api.example.test/api/devices')).rejects.toThrow('确认服务连接与账户状态');
    expect(fetch).not.toHaveBeenCalled();
  });
});

const user: AccountUser = { id: 'member', issuer: 'https://auth.example.test', subject: 'sub', display_name: 'Member', email: null, role: 'operator', disabled: false };
function session(context = 'session-a') {
  updateAccount({ status: 'ready', config: { mode: 'oidc', login_enabled: true, desktop_login_enabled: true }, session: { authenticated: true, mode: 'oidc', user, csrf_token: 'csrf-a', session_context: context, expires_at: null }, error: '' });
}

describe('OIDC request boundaries', () => {
  beforeEach(() => { sessionStorage.clear(); config.baseURL = window.location.origin; resetAccount(); session(); vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}'))); });
  afterEach(() => { resetAccount(); vi.unstubAllGlobals(); });
  it('uses same-origin Cookies, server CSRF and session context without exposing the legacy key', async () => {
    setServiceKey('legacy-admin-secret');
    await authenticatedFetch(`${config.baseURL}/api/devices`, { method: 'POST', headers: { Authorization: 'untrusted', 'X-R-Link-CSRF': 'untrusted', 'X-R-Link-Session-Context': 'untrusted' } });
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(init?.credentials).toBe('same-origin'); expect(init?.redirect).toBe('error');
    const headers = new Headers(init?.headers);
    expect(headers.has('Authorization')).toBe(false); expect(headers.get('X-R-Link-CSRF')).toBe('csrf-a'); expect(headers.get('X-R-Link-Session-Context')).toBe('session-a');
  });
  it('refuses Cookie login on another service origin', async () => {
    config.baseURL = 'https://api.example.test'; session();
    await expect(authenticatedFetch('https://api.example.test/api/devices')).rejects.toThrow('需要在服务网页或桌面客户端登录');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('uses only the in-memory R-Link session for desktop requests', async () => {
    config.baseURL = 'https://api.example.test/r-link'; session(); setDesktopSessionToken('desktop-session');
    await authenticatedFetch(`${config.baseURL}/api/devices`);
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer desktop-session'); expect(init?.credentials).toBe('omit');
    expect(sessionStorage.length).toBe(0); expect(localStorage.getItem('desktop-session')).toBeNull();
    await expect(authenticatedFetch('https://api.example.test/account/api')).rejects.toThrow('路径之外');
  });
  it('discards a late response and cancels requests when the same account receives a new session', async () => {
    let complete!: (response: Response) => void;
    vi.mocked(fetch).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
    const pending = authenticatedFetch(`${config.baseURL}/api/devices`);
    const revision = getAccountState().revision;
    localStorage.setItem(`r-link-topology:v1:${window.location.origin}`, JSON.stringify({ annotations: { private: 'Old member note' } }));
    session('session-b');
    expect(getAccountState().revision).toBeGreaterThan(revision);
    expect(vi.mocked(fetch).mock.calls[0][1]?.signal?.aborted).toBe(true);
    expect(localStorage.getItem(`r-link-topology:v1:${window.location.origin}`)).not.toBeNull();
    complete(new Response('[]'));
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
  it.each([401, 409])('clears account state on HTTP %s without falling back to a service key', async status => {
    setServiceKey('legacy-admin-secret'); vi.mocked(fetch).mockResolvedValue(new Response('{"detail":"Session expired"}', { status }));
    await expect(authenticatedFetch(`${config.baseURL}/api/devices`)).rejects.toThrow('Session expired');
    expect(getAccountState().session?.authenticated).toBe(false);
    expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).has('Authorization')).toBe(false);
  });
});
