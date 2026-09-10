import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
const state = vi.hoisted(() => ({ configured: true, getSession: vi.fn() }));
vi.mock('./config', () => ({ API_CONFIG: { baseURL: 'https://api.example.test' } }));
vi.mock('../utils/supabase/client', () => ({
  get supabaseConfigured() { return state.configured; },
  supabase: { auth: { getSession: state.getSession } },
}));
import { authenticatedFetch } from './authenticated-fetch';

describe('authenticated API requests', () => {
  beforeEach(() => {
    state.configured = true;
    state.getSession.mockReset().mockResolvedValue({ data: { session: { access_token: 'first' } }, error: null });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));
  });
  afterEach(() => vi.unstubAllGlobals());
  it('reads the current session for every request and keeps caller headers', async () => {
    await authenticatedFetch('https://api.example.test/api/plugins/', { headers: new Headers({ 'X-Trace': '1', Authorization: 'stale' }) });
    state.getSession.mockResolvedValue({ data: { session: { access_token: 'refreshed' } }, error: null });
    await authenticatedFetch('https://api.example.test/api/system/info');
    const calls = vi.mocked(fetch).mock.calls;
    expect(new Headers(calls[0][1]?.headers).get('Authorization')).toBe('Bearer first');
    expect(new Headers(calls[0][1]?.headers).get('X-Trace')).toBe('1');
    expect(new Headers(calls[1][1]?.headers).get('Authorization')).toBe('Bearer refreshed');
    expect(calls[0][1]?.redirect).toBe('error');
  });
  it('does not send management requests without a session', async () => {
    state.getSession.mockResolvedValue({ data: { session: null }, error: null });
    await expect(authenticatedFetch('https://api.example.test/api/plugins/')).rejects.toThrow('请先登录');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('rejects an unrelated origin before reading credentials', async () => {
    await expect(authenticatedFetch('https://elsewhere.example/api/plugins/')).rejects.toThrow('未配置');
    expect(state.getSession).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });
  it('does not contact an old provider when configuration is missing', async () => {
    state.configured = false;
    await expect(authenticatedFetch('https://api.example.test/api/plugins/')).rejects.toThrow('配置登录');
    expect(state.getSession).not.toHaveBeenCalled();
  });
  it('surfaces a server denial instead of reporting a successful operation', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('{"detail":"Invalid authentication credentials"}', { status: 401 }));
    await expect(authenticatedFetch('https://api.example.test/api/console/start', { method: 'POST' })).rejects.toThrow('Invalid authentication');
  });
});
