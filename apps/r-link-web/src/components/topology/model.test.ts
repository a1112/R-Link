import { expect, it } from 'vitest';
import type { Device } from '../../api/devices';
import type { RFileStatus } from '../../api/rfile';
import { makeNodes, filterNodes, layoutNodes, type MeshSnapshot, virtualIp, type FabricSnapshot } from './model';
import type { ClientDeviceInfo } from '../../api/client-device';
import type { NativeFabricStatus } from '../../api/fabric';

const device: Device = { id: 'nas', name: 'Family NAS', host: '192.0.2.8', port: 22, username: 'owner', revision: 1, status: 'reachable', latency_ms: 4, checked_at: null, device_type: 'nas', platform: 'linux' };
const rfile = { network: { state: 'online' }, devices: [{ deviceId: 'nas', deviceName: 'Bridge peer', presence: 'online', platform: 'windows' }] } as RFileStatus;
const connectedClient: ClientDeviceInfo = { hostname: 'lcx_ace', platform: 'windows', runtime: 'desktop', netbird: { daemonStatus: 'Connected', management: { url: 'https://175.178.16.90:7443', connected: true }, signal: { connected: true }, netbirdIp: '100.126.3.139/16' } };
const currentMesh: MeshSnapshot = { status: { configured: true, reachable: true, management_url: 'https://175.178.16.90:7443', peers: 1, connected: 1, reason: null }, peers: [{ id: 'peer-current', name: 'lcx_ace', ip: '100.126.3.139', ipv6: null, connected: true, last_seen: null, os: 'windows', groups: [] }] };
const registeredClient: Device = { ...device, id: 'registered-client', name: 'Registered LCX', host: '100.126.3.139', source: 'netbird', peer_id: 'peer-current', connection_status: 'online' };
function fabricProof() {
  const now = Date.now() / 1000;
  const local: NativeFabricStatus = { schema_version: 1, provider: 'rlink-fabric', device_id: 'local-fabric-peer', name: 'lcx_ace', control_url: 'https://cloud.example/r-link', control: { connected: true, last_success_at: now }, tun: { ready: true, name: 'RLink', ip: '10.66.0.2/24' }, updated_at: now, mode: 'vpn', peers: [{ peer_id: 'remote-fabric-peer', ip: '10.66.0.3', path: 'relay', rtt_ms: 10, last_handshake: now, handshake_age_seconds: 0, rx_bytes: 5, tx_bytes: 5 }] };
  const snapshot: FabricSnapshot = { status: { schema_version: 1, provider: 'rlink', configured: true, control_url: local.control_url!, peers: 1, connected: 1, config_version: 1, mode: 'direct+relay', mode_transport: 'vpn', capabilities: { enrollment: true, revocation: true, groups: true, p2p: true, relay: true, policies: false, networks: false, vpn: true } }, peers: [{ id: 'local-fabric-peer', peer_id: 'local-fabric-peer', name: 'Registered Fabric', os: 'windows', ip: '10.66.0.2', public_key: 'public', groups: [], mode: 'vpn', connected: true, control_connected: true, relay_connected: true, tunnel_ready_reported: true, data_plane_confirmed: true, last_seen: now, paths: [] }] };
  const registered: Device = { ...device, id: 'fabric-device', name: 'Registered Fabric', source: 'fabric', peer_id: local.device_id, host: '10.66.0.2', provider_url: `${local.control_url}#rlink-fabric`, connection_status: 'online' };
  return { client: { ...connectedClient, netbird: null, fabric: local }, snapshot, registered };
}

it('confirms and merges only a fresh Fabric VPN with real TUN, matching UUID/control URL and real handshake', () => {
  const { client, snapshot, registered } = fabricProof();
  const nodes = makeNodes([registered], null, client, null, snapshot);
  expect(nodes).toHaveLength(1); expect(nodes[0].device).toBe(registered);
  expect(nodes[0].clientFabric?.confirmed).toBe(true); expect(nodes[0].statusLabel).toBe('自研 VPN 握手已确认');
  expect(nodes[0].clientMesh?.confirmed).toBe(false);
});

it('does not label transport tests as VPN or override a separately proven NetBird connection', () => {
  const { client, snapshot, registered } = fabricProof(); client.fabric.mode = 'transport-test';
  const unverified = makeNodes([registered], null, client, null, snapshot);
  expect(unverified).toHaveLength(2); expect(unverified[0].status).toBe('unknown'); expect(unverified[0].clientFabric?.confirmed).toBe(false);
  const independent = makeNodes([], null, { ...client, netbird: connectedClient.netbird }, currentMesh, snapshot)[0];
  expect(independent.status).toBe('online'); expect(independent.clientMesh?.confirmed).toBe(true); expect(independent.clientFabric?.confirmed).toBe(false);
});

it('rejects stale Fabric samples, missing real handshakes and manual same-IP impersonation', () => {
  const { client, snapshot, registered } = fabricProof();
  for (const bad of [ { ...client, fabric: { ...client.fabric, updated_at: 1 } }, { ...client, fabric: { ...client.fabric, peers: [] } }, { ...client, fabric: { ...client.fabric, control_url: 'https://other.example/r-link' } } ]) {
    const nodes = makeNodes([registered], null, bad, null, snapshot);
    expect(nodes[0].status).toBe('unknown'); expect(nodes[0].device).toBeUndefined();
  }
  for (const bad of [ { ...registered, source: 'manual' as const }, { ...registered, peer_id: 'other-peer' }, { ...registered, provider_url: 'https://other.example/r-link#rlink-fabric' }, { ...registered, connection_status: 'revoked' as const } ]) {
    const nodes = makeNodes([bad], null, client, null, snapshot);
    expect(nodes).toHaveLength(2); expect(nodes[0].device).toBeUndefined();
  }
});

it('confirms only the local Agent connection, virtual IP and exact current reachable controlplane', () => {
  const node = makeNodes([], null, connectedClient, currentMesh)[0];
  expect(node.name).toBe('本电脑'); expect(node.status).toBe('online'); expect(node.statusLabel).toContain('已入网');
  expect(node.clientMesh?.ip).toBe('100.126.3.139'); expect(node.clientMesh?.confirmed).toBe(true);
  expect(node.clientMesh?.reason).toContain('不代表节点之间 P2P');
});

it.each([
  { ...connectedClient, runtime: 'browser' as const },
  { ...connectedClient, netbird: null },
  { ...connectedClient, netbird: { ...connectedClient.netbird!, daemonStatus: 'Disconnected' } },
  { ...connectedClient, netbird: { ...connectedClient.netbird!, management: { ...connectedClient.netbird!.management, connected: false } } },
  { ...connectedClient, netbird: { ...connectedClient.netbird!, signal: { connected: false } } },
  { ...connectedClient, netbird: { ...connectedClient.netbird!, netbirdIp: '127.0.0.1/16' } },
  { ...connectedClient, netbird: { ...connectedClient.netbird!, management: { url: 'https://175.178.16.90:7444', connected: true } } },
])('keeps the client unknown when its own proof is incomplete or belongs to another controlplane %#', client => {
  const nodes = makeNodes([registeredClient], null, client, currentMesh);
  expect(nodes[0].status).toBe('unknown'); expect(nodes[0].device).toBeUndefined(); expect(nodes).toHaveLength(2);
});

it('does not confirm membership when the current management service is unavailable', () => {
  const nodes = makeNodes([registeredClient], null, connectedClient, { ...currentMesh, status: { ...currentMesh.status, reachable: false } });
  expect(nodes[0].status).toBe('unknown'); expect(nodes[0].device).toBeUndefined(); expect(nodes).toHaveLength(2);
});

it('merges a proven online direct current peer without double counting, and preserves gateway edges', () => {
  const nodes = makeNodes([registeredClient, { ...device, id: 'behind-client', source: 'gateway', gateway_id: registeredClient.id }], null, connectedClient, currentMesh);
  expect(nodes).toHaveLength(2); expect(nodes[0].device).toBe(registeredClient); expect(nodes[0].source).toBe('client');
  expect(layoutNodes(nodes).edges.find(edge => edge.to === 'device:behind-client')?.from).toBe('client:current');
  expect(filterNodes(nodes, { query: '100.126.3.139', status: 'all', type: 'all', source: 'all' })).toHaveLength(1);
});

it.each([
  { ...registeredClient, source: 'manual' as const },
  { ...registeredClient, source: 'gateway' as const },
  { ...registeredClient, gateway_id: 'another-gateway' },
  { ...registeredClient, connection_status: 'offline' as const },
  { ...registeredClient, connection_status: 'revoked' as const },
  { ...registeredClient, peer_id: 'different-peer' },
])('never lets manual, gateway, stale or unrelated same-IP inventory impersonate this computer %#', inventory => {
  const nodes = makeNodes([inventory], null, connectedClient, currentMesh);
  expect(nodes).toHaveLength(2); expect(nodes[0].device).toBeUndefined(); expect(nodes[1].device).toBe(inventory);
});

it('keeps stale inventory separate when that peer is not actually online in the current controlplane', () => {
  const nodes = makeNodes([registeredClient], null, connectedClient, { ...currentMesh, peers: [{ ...currentMesh.peers[0], connected: false }] });
  expect(nodes[0].status).toBe('online'); expect(nodes[0].device).toBeUndefined(); expect(nodes).toHaveLength(2);
});

it.each(['hostname', '100.126.3.999/16', '100.126.3.139/99', '0.0.0.0', '224.0.0.1', '::1', 'fe80::1', '100.126.3.139/16/16'])('rejects a non-unicast or invalid virtual address %s', value => {
  expect(virtualIp(value)).toBeNull();
});

it('represents the actual client separately with an unverified mesh state and management relation', () => {
  const nodes = makeNodes([], null, { hostname: 'lcx_ace', platform: 'windows', runtime: 'desktop' });
  expect(nodes[0].name).toBe('本电脑');
  expect(nodes[0].subtitle).toBe('lcx_ace');
  expect(nodes[0].status).toBe('unknown');
  expect(nodes[0].device).toBeUndefined();
  expect(layoutNodes(nodes).edges[0].relation).toBe('client');
  expect(filterNodes(nodes, { query: 'lcx_ace', status: 'all', source: 'client', type: 'computer' })).toHaveLength(1);
});

it('represents the actual client separately with an unverified mesh state and management relation', () => {
  const nodes = makeNodes([], null, { hostname: 'lcx_ace', platform: 'windows', runtime: 'desktop' });
  expect(nodes[0].name).toBe('本电脑');
  expect(nodes[0].subtitle).toBe('lcx_ace');
  expect(nodes[0].status).toBe('unknown');
  expect(nodes[0].device).toBeUndefined();
  expect(layoutNodes(nodes).edges[0].relation).toBe('client');
  expect(filterNodes(nodes, { query: 'lcx_ace', status: 'all', source: 'client', type: 'computer' })).toHaveLength(1);
});

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
