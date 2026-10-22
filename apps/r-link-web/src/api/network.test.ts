import { expect, it } from 'vitest';
import { defaultNetworkInterface, trafficRate, type NetworkSnapshot } from './network';
const sample = (time: number, sent: number, received: number): NetworkSnapshot => ({ hostname: 'server', sampled_at: time, boot_time: 1, interfaces: [{ name: 'eth0', is_up: true, addresses: ['192.0.2.1'], bytes_sent: sent, bytes_recv: received }] });
it('calculates Mbps using elapsed seconds and actual byte deltas', () => {
  const rate = trafficRate(sample(10, 100, 100), sample(12, 250100, 500100), 'eth0');
  expect(rate?.upload).toBe(1);
  expect(rate?.download).toBe(2);
});
it('prefers an active addressed interface over loopback and link-local interfaces', () => {
  const ethernet = sample(1, 1, 1).interfaces[0];
  const snapshot = { ...sample(1, 1, 1), interfaces: [
    { ...ethernet, name: 'lo0', addresses: ['127.0.0.1', '::1', 'fe80::1%lo0'] },
    { ...ethernet, name: 'awdl0', addresses: ['fe80::123%awdl0'] },
    { ...ethernet, name: 'en0', addresses: ['192.168.2.233'] },
  ] };
  expect(defaultNetworkInterface(snapshot)).toBe('en0');
  expect(defaultNetworkInterface({ ...snapshot, interfaces: [] })).toBe('');
  expect(defaultNetworkInterface(null)).toBe('');
});
it('rejects resets, restarts, missing interfaces and stale sample gaps', () => {
  expect(trafficRate(sample(10, 100, 100), sample(12, 1, 1), 'eth0')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), { ...sample(12, 10, 10), boot_time: 2 }, 'eth0')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), sample(90, 10, 10), 'eth0')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), sample(12, 10, 10), 'gone')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), sample(NaN, 10, 10), 'eth0')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), sample(12, Infinity, 10), 'eth0')).toBeNull();
});
