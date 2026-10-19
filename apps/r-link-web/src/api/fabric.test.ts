import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { fabricApi, getNativeFabricStatus, nativeFabricFresh } from './fabric';
import { invoke } from '@tauri-apps/api/core';
import { http } from './client';
vi.mock('./client', () => ({ http: { get: vi.fn(), post: vi.fn() } }));
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => { delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__; });

it('creates only a one-off enrollment through the authenticated HTTP client', async () => {
  await fabricApi.createEnrollment({ name: 'Mac Air', groups: ['rlink-devices'], ttl_seconds: 3600 });
  expect(http.post).toHaveBeenCalledWith('/api/fabric/enrollments', { name: 'Mac Air', groups: ['rlink-devices'], ttl_seconds: 3600, uses: 1 }, { signal: undefined });
  await fabricApi.revokeEnrollment('unsafe/id');
  expect(http.post).toHaveBeenLastCalledWith('/api/fabric/enrollments/unsafe%2Fid/revoke', undefined, { signal: undefined });
});

it('does not look up the native Agent from a browser or invent a missing native command', async () => {
  expect(await getNativeFabricStatus()).toBeNull(); expect(invoke).not.toHaveBeenCalled();
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
  vi.mocked(invoke).mockRejectedValue(new Error('unknown command'));
  expect(await getNativeFabricStatus()).toBeNull(); expect(invoke).toHaveBeenCalledWith('desktop_fabric_info');
});

it('rejects future or stale snapshots even when connected is true', () => {
  const sample = { schema_version: 1, provider: 'rlink-fabric', updated_at: 100, mode: 'transport-test' } as Parameters<typeof nativeFabricFresh>[0];
  expect(nativeFabricFresh(sample, 130)).toBe(true); expect(nativeFabricFresh(sample, 146)).toBe(false); expect(nativeFabricFresh(sample, 90)).toBe(false);
});
