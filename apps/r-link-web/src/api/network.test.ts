import { expect, it } from 'vitest';
import { trafficRate, type NetworkSnapshot } from './network';
const sample = (time: number, sent: number, received: number): NetworkSnapshot => ({ hostname: 'server', sampled_at: time, boot_time: 1, interfaces: [{ name: 'eth0', is_up: true, addresses: ['192.0.2.1'], bytes_sent: sent, bytes_recv: received }] });
it('calculates Mbps using elapsed seconds and actual byte deltas', () => {
  const rate = trafficRate(sample(10, 100, 100), sample(12, 250100, 500100), 'eth0');
  expect(rate?.upload).toBe(1);
  expect(rate?.download).toBe(2);
});
it('rejects resets, restarts, missing interfaces and stale sample gaps', () => {
  expect(trafficRate(sample(10, 100, 100), sample(12, 1, 1), 'eth0')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), { ...sample(12, 10, 10), boot_time: 2 }, 'eth0')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), sample(90, 10, 10), 'eth0')).toBeNull();
  expect(trafficRate(sample(10, 1, 1), sample(12, 10, 10), 'gone')).toBeNull();
});
