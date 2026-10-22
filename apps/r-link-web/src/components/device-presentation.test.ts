import { expect, it } from 'vitest';
import { deviceAccessMode, deviceWebUrl } from './device-presentation';
import type { Device } from '../api/devices';
const device: Device = { id: 'one', name: 'Test', host: 'nas.example', port: 443, username: '', revision: 1, status: 'unchecked', checked_at: null, latency_ms: null };
it('keeps legacy manual SSH while missing capabilities on synced peers are none', () => {
  expect(deviceAccessMode(device)).toBe('ssh');
  expect(deviceAccessMode({ ...device, source: 'netbird' })).toBe('none');
  expect(deviceAccessMode({ ...device, access_mode: 'ssh', connection_status: 'removed' })).toBe('none');
  expect(deviceAccessMode({ ...device, access_mode: 'ssh', connection_status: 'revoked' })).toBe('none');
});
it('constructs explicit IPv6 web addresses without credentials, paths or scheme injection', () => {
  expect(deviceWebUrl({ ...device, host: '2001:db8::1', access_mode: 'web', web_scheme: 'https' })).toBe('https://[2001:db8::1]:443/');
  for (const host of ['evil.example/path', 'owner@evil.example', 'evil.example?x=1', 'evil.example#x', 'evil.example\\path', 'https://evil.example', '[::1]', 'evil.example:80', ' bad.example']) {
    expect(deviceWebUrl({ ...device, host, access_mode: 'web', web_scheme: 'https' }), host).toBeNull();
  }
  expect(deviceWebUrl({ ...device, access_mode: 'none' })).toBeNull();
});
