import { afterEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { getClientDeviceInfo } from './client-device';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
afterEach(() => { delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__; vi.resetAllMocks(); });

it('keeps browser identity local without using the service hostname', async () => {
  expect(await getClientDeviceInfo()).toEqual({ hostname: null, platform: 'unknown', runtime: 'browser' });
  expect(invoke).not.toHaveBeenCalled();
});

it('reads the desktop host from the native process and tolerates older clients', async () => {
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
  vi.mocked(invoke).mockResolvedValueOnce({ hostname: 'lcx_ace', platform: 'windows' }).mockRejectedValueOnce(new Error('unknown command'));
  expect(await getClientDeviceInfo()).toEqual({ hostname: 'lcx_ace', platform: 'windows', runtime: 'desktop' });
  expect(await getClientDeviceInfo()).toEqual({ hostname: null, platform: 'unknown', runtime: 'desktop' });
});

it('keeps only public Agent status fields from native sampling', async () => {
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
  vi.mocked(invoke).mockResolvedValue({ hostname: 'lcx_ace', platform: 'windows', netbird: { daemonStatus: 'Connected', management: { url: 'https://175.178.16.90:7443', connected: true, error: 'private details' }, signal: { connected: true, error: 'private details' }, netbirdIp: '100.126.3.139/16', PrivateKey: 'never expose', peers: { details: [] } } });
  expect(await getClientDeviceInfo()).toEqual({ hostname: 'lcx_ace', platform: 'windows', runtime: 'desktop', netbird: { daemonStatus: 'Connected', management: { url: 'https://175.178.16.90:7443', connected: true }, signal: { connected: true }, netbirdIp: '100.126.3.139/16' } });
});

it('reports an unavailable Agent without assigning the service hostname or claiming connectivity', async () => {
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
  vi.mocked(invoke).mockResolvedValue({ hostname: 'lcx_ace', platform: 'windows', netbird: null });
  expect((await getClientDeviceInfo()).netbird).toBeNull();
});
