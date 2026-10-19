import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { devicesApi } from './devices';
import { updateAccount } from './account-access';
beforeEach(() => updateAccount({ status: 'ready', config: { mode: 'local', login_enabled: false, desktop_login_enabled: false }, session: null, error: '' }));
afterEach(() => { vi.unstubAllGlobals(); });
it('uses authenticated API paths and encoded identifiers for device management actions', async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response('{}', { status: 200 }));
  vi.stubGlobal('fetch', fetcher);
  await devicesApi.managementStatus();
  await devicesApi.sync();
  await devicesApi.onboarding();
  await devicesApi.link('device/a', 'peer-one');
  await devicesApi.revoke('device/a');
  await devicesApi.export(2);
  await devicesApi.export();
  const paths = fetcher.mock.calls.map(([url]) => new URL(String(url), 'http://localhost').pathname + new URL(String(url), 'http://localhost').search);
  expect(paths).toEqual(['/api/devices/management-status', '/api/devices/sync', '/api/devices/onboarding', '/api/devices/device%2Fa/link', '/api/devices/device%2Fa/revoke', '/api/devices/export?version=2', '/api/devices/export']);
  expect(fetcher.mock.calls[3][1].body).toBe(JSON.stringify({ peer_id: 'peer-one' }));
});
