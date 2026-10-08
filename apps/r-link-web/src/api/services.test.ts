import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { servicesApi } from './services';
import { setServiceUrl } from './service-url';
import { setServiceKey } from './service-access';
import { updateAccount } from './account-access';
const legacy = () => updateAccount({ status: 'ready', config: { mode: 'service', login_enabled: false, desktop_login_enabled: false }, session: null, error: '' });

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  setServiceUrl('https://cloud.example.test');
  setServiceKey('cloud-key');
  legacy();
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => new Response('{}')));
});
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

it('sends service management requests through the cloud API namespace', async () => {
  await servicesApi.capabilities();
  await servicesApi.tunnels();
  await servicesApi.tunnelAction('tunnel-id', 'start');
  await servicesApi.domains();
  await servicesApi.domainAction('apply');
  await servicesApi.dns('domain-id');
  await servicesApi.downloads();
  await servicesApi.createDownload('https://example.test/file.zip', 'file.zip');
  await servicesApi.downloadAction('download-id', 'pause');
  expect(vi.mocked(fetch).mock.calls.map(([url]) => new URL(String(url)).pathname)).toEqual([
    '/api/services', '/api/tunnels', '/api/tunnels/tunnel-id/start',
    '/api/domains', '/api/domains/service/apply', '/api/domains/domain-id/dns',
    '/api/downloads', '/api/downloads', '/api/downloads/download-id/pause',
  ]);
  for (const [url, init] of vi.mocked(fetch).mock.calls) {
    expect(new URL(String(url)).origin).toBe('https://cloud.example.test');
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer cloud-key');
  }
});

it('downloads from the current cloud API with only that origin’s key', async () => {
  setServiceUrl('https://second.example.test');
  legacy();
  vi.mocked(fetch).mockResolvedValueOnce(new Response('first file'));
  expect((await servicesApi.downloadFile('download-id')).size).toBe(10);
  expect(fetch).toHaveBeenLastCalledWith('https://second.example.test/api/downloads/download-id/file', expect.any(Object));
  expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).has('Authorization')).toBe(false);
  setServiceKey('second-key');
  legacy();
  vi.mocked(fetch).mockResolvedValueOnce(new Response('second file'));
  expect((await servicesApi.downloadFile('download-id')).size).toBe(11);
  expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer second-key');
});
