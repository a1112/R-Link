import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  calculateTrafficDelta,
  connectionProcess,
  connectionProtocol,
  filterTrafficConnections,
  type ClashTrafficSnapshot,
} from './traffic';

const connection = (overrides: Record<string, unknown> = {}) => ({
  id: 'c1',
  start: '2026-10-11T00:00:00Z',
  upload: 100,
  download: 200,
  chains: ['Proxy'],
  rule: 'MATCH',
  metadata: {
    network: 'tcp',
    type: 'HTTP',
    sourceIP: '10.0.0.2',
    sourcePort: 1234,
    destinationIP: '203.0.113.10',
    destinationPort: 443,
    host: 'example.com',
    process: 'Browser',
  },
  ...overrides,
});

const snapshot = (overrides: Partial<ClashTrafficSnapshot> = {}): ClashTrafficSnapshot => ({
  sampled_at: 100,
  source_id: 'api-server-a',
  downloadTotal: 1_000,
  uploadTotal: 500,
  connections: [connection()],
  total_connections: 1,
  truncated: false,
  ...overrides,
});

afterEach(() => vi.restoreAllMocks());

describe('calculateTrafficDelta', () => {
  it('waits for a baseline and calculates total and per-connection bytes per second', () => {
    const first = snapshot();
    const second = snapshot({
      sampled_at: 102,
      downloadTotal: 1_400,
      uploadTotal: 700,
      connections: [connection({ download: 260, upload: 140 })],
    });

    expect(calculateTrafficDelta(null, first)).toMatchObject({ ready: false, reason: 'initial' });
    expect(calculateTrafficDelta(first, second)).toMatchObject({
      ready: true,
      elapsedSeconds: 2,
      downloadBps: 200,
      uploadBps: 100,
      connectionRates: { c1: { downloadBps: 30, uploadBps: 20 } },
    });
  });

  it('resets on target changes, counter rollback, and a long sampling gap', () => {
    const first = snapshot();
    expect(calculateTrafficDelta(first, snapshot({ source_id: 'api-server-b', sampled_at: 102 })).reason).toBe('target_changed');
    expect(calculateTrafficDelta(first, snapshot({ sampled_at: 102, downloadTotal: 900 })).reason).toBe('counter_reset');
    expect(calculateTrafficDelta(first, snapshot({ sampled_at: 131 })).reason).toBe('stale');
  });

  it('leaves a new connection without a rate until its next sample', () => {
    const first = snapshot();
    const second = snapshot({ sampled_at: 102, connections: [connection({ id: 'new', download: 10, upload: 10 })] });
    const result = calculateTrafficDelta(first, second);
    expect(result.ready).toBe(true);
    expect(result.connectionRates.new).toBeNull();
  });

  it('does not reuse a connection id when its start time changes', () => {
    const first = snapshot();
    const reusedId = snapshot({
      sampled_at: 102,
      connections: [connection({ start: '2026-10-11T00:01:00Z', download: 260, upload: 140 })],
    });
    const result = calculateTrafficDelta(first, reusedId);

    expect(result.ready).toBe(true);
    expect(result.connectionRates.c1).toBeNull();
    expect(result.downloadBps).toBe(0);
  });
});

describe('traffic connection filters', () => {
  it('searches host, source, and optional process while filtering protocol', () => {
    const browser = connection();
    const terminal = connection({
      id: 'c2',
      metadata: { ...browser.metadata, sourceIP: '10.0.0.3', host: 'updates.example.net', network: 'udp', type: 'HTTP', process: 'Terminal' },
    });
    expect(filterTrafficConnections([browser, terminal], 'browser', '')).toHaveLength(1);
    expect(filterTrafficConnections([browser, terminal], '10.0.0.2:1234', '')).toHaveLength(1);
    expect(filterTrafficConnections([browser, terminal], '', 'udp').map(item => item.id)).toEqual(['c2']);
    expect(filterTrafficConnections([browser, terminal], 'missing', '')).toEqual([]);
    expect(connectionProcess(terminal)).toBe('Terminal');
    expect(connectionProtocol(terminal)).toBe('udp');
  });
});
