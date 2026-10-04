import { expect, it } from 'vitest';
import type { Device } from '../../api/devices';
import type { RFileStatus } from '../../api/rfile';
import { makeNodes, filterNodes, layoutNodes } from './model';

const device: Device = { id: 'nas', name: 'Family NAS', host: '192.0.2.8', port: 22, username: 'owner', revision: 1, status: 'reachable', latency_ms: 4, checked_at: null, device_type: 'nas', platform: 'linux' };
const rfile = { network: { state: 'online' }, devices: [{ deviceId: 'nas', deviceName: 'Bridge peer', presence: 'online', platform: 'windows' }] } as RFileStatus;

it('never infers device presence from a reachable port or an online gateway', () => {
  const nodes = makeNodes([device, { ...device, id: 'child', source: 'gateway', gateway_status: 'online' }, { ...device, id: 'revoked', connection_status: 'revoked' }], null);
  expect(nodes.map(node => node.status)).toEqual(['unknown', 'unknown', 'unknown']);
  expect(nodes[2].statusLabel).toBe('已撤销');
});

it('keeps source identities distinct and clears unverified bridge presence', () => {
  const nodes = makeNodes([{ ...device, connection_status: 'offline' }], rfile);
  expect(new Set(nodes.map(node => node.id)).size).toBe(2);
  expect(nodes.map(node => node.status)).toEqual(['offline', 'online']);
  expect(makeNodes([], { ...rfile, network: { ...rfile.network, state: 'offline' } })[0].status).toBe('unknown');
});

it('filters names, addresses, tags and sources without changing the input', () => {
  const nodes = makeNodes([{ ...device, connection_status: 'online', tags: ['home'] }], rfile);
  expect(filterNodes(nodes, { query: 'HOME', status: 'online', type: 'nas', source: 'inventory' })).toHaveLength(1);
  expect(filterNodes(nodes, { query: '192.0.2.8', status: 'all', type: 'all', source: 'all' })).toHaveLength(1);
  expect(filterNodes(nodes, { query: '', status: 'offline', type: 'all', source: 'all' })).toHaveLength(0);
  expect(nodes).toHaveLength(2);
});

it('draws a child under its real gateway and never substitutes a filtered-out parent', () => {
  const nodes = makeNodes([device, { ...device, id: 'child', gateway_id: 'nas', source: 'gateway' }], null);
  expect(layoutNodes(nodes).edges.find(edge => edge.to === nodes[1].id)?.from).toBe(nodes[0].id);
  expect(layoutNodes([nodes[1]]).edges).toHaveLength(0);
});

it('fits a small inventory around its content instead of shrinking cards into empty space', () => {
  const layout = layoutNodes(makeNodes([device], null));
  expect(layout.width).toBeLessThanOrEqual(620);
  expect(layout.height).toBeLessThanOrEqual(220);
});

it.each([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 32, 256])('lays out %i nodes without overlap or clipping', count => {
  const nodes = makeNodes(Array.from({ length: count }, (_, i) => ({ ...device, id: String(i) })), null);
  const layout = layoutNodes(nodes);
  const points = [...layout.nodes, layout.hub];
  for (const point of points) {
    expect(point.x - 106).toBeGreaterThanOrEqual(0);
    expect(point.y - 56).toBeGreaterThanOrEqual(0);
    expect(point.x + 106).toBeLessThanOrEqual(layout.width);
    expect(point.y + 56).toBeLessThanOrEqual(layout.height);
  }
  for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
    expect(Math.abs(points[i].x - points[j].x) >= 224 || Math.abs(points[i].y - points[j].y) >= 124).toBe(true);
  }
});
