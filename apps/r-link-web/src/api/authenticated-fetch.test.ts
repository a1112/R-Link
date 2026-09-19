import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
const config = vi.hoisted(() => ({ baseURL: 'https://api.example.test' }));
vi.mock('./config', () => ({ API_CONFIG: config }));
import { authenticatedFetch } from './authenticated-fetch';
import { getServiceKey, setServiceKey } from './service-access';

describe('service API requests', () => {
  beforeEach(() => {
    sessionStorage.clear();
    config.baseURL = 'https://api.example.test';
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
});
