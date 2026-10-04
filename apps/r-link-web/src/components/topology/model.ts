import type { Device, DeviceType } from '../../api/devices';
import type { RFileDevice, RFileStatus } from '../../api/rfile';
import { connectionLabels, devicePlatforms, deviceTypes, sourceLabels } from '../device-presentation';

export type Presence = 'online' | 'offline' | 'unknown';
export type TopologyNode = {
  id: string; name: string; subtitle: string; type: DeviceType; source: 'inventory' | 'rfile';
  sourceLabel: string; status: Presence; statusLabel: string; parentId: string | null;
  device?: Device; peer?: RFileDevice;
};
export type Filters = { query: string; status: 'all' | Presence; type: string; source: string };
export const presenceLabels: Record<Presence, string> = { online: '在线', offline: '离线', unknown: '未知' };
const presence = (value?: string): Presence => value === 'online' || value === 'offline' ? value : 'unknown';

export function makeNodes(devices: Device[], rfile: RFileStatus | null): TopologyNode[] {
  return [
    ...devices.map((device): TopologyNode => ({
      id: `device:${device.id}`, name: device.name, type: device.device_type ?? 'other', source: 'inventory',
      subtitle: `${devicePlatforms[device.platform ?? 'unknown']} · ${deviceTypes[device.device_type ?? 'other']}`,
      sourceLabel: sourceLabels[device.source ?? 'manual'], status: presence(device.connection_status),
      statusLabel: connectionLabels[device.connection_status ?? 'unknown'],
      parentId: device.source === 'gateway' ? (device.gateway_id ? `device:${device.gateway_id}` : null) : 'current', device,
    })),
    ...(rfile?.devices ?? []).map((peer): TopologyNode => {
      const status = rfile?.network.state === 'online' ? presence(peer.presence) : 'unknown';
      const type = peer.deviceType === 'nas' ? 'nas' : peer.deviceType === 'server' ? 'server'
        : ['android', 'ios', 'ipados'].includes(peer.platform ?? '') ? 'mobile'
        : ['windows', 'macos', 'linux'].includes(peer.platform ?? '') ? 'computer' : 'other';
      return { id: `rfile:${peer.deviceId}`, name: peer.deviceName || peer.deviceId, subtitle: peer.platform || '未知平台', type,
        source: 'rfile', sourceLabel: 'R-File', status, statusLabel: presenceLabels[status], parentId: 'current', peer };
    }),
  ];
}

export function filterNodes(nodes: TopologyNode[], filters: Filters) {
  const query = filters.query.trim().toLocaleLowerCase();
  return nodes.filter(node => (filters.status === 'all' || node.status === filters.status)
    && (filters.type === 'all' || node.type === filters.type)
    && (filters.source === 'all' || node.source === filters.source)
    && [node.name, node.subtitle, node.device?.host, ...(node.device?.tags ?? []), ...(node.device?.mesh_groups ?? []).map(group => group.name)]
      .join(' ').toLocaleLowerCase().includes(query));
}

export function layoutNodes(nodes: TopologyNode[]) {
  const large = nodes.length > 8;
  const hub = { id: 'current', x: 540, y: large ? 100 : 380 };
  const positioned = nodes.map((node, index) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / Math.max(1, nodes.length);
    return { ...node, x: large ? 170 + (index % 3) * 370 : 540 + Math.sin(angle) * 340,
      y: large ? 290 + Math.floor(index / 3) * 152 : 380 + Math.cos(angle) * 180 };
  });
  // Fit the actual card bounds, including the server, with a small breathing margin.
  const points = [...positioned, hub];
  const left = Math.min(...points.map(point => point.x)) - 134;
  const top = Math.min(...points.map(point => point.y)) - 84;
  const width = Math.max(...points.map(point => point.x)) + 134 - left;
  const height = Math.max(...points.map(point => point.y)) + 84 - top;
  points.forEach(point => { point.x -= left; point.y -= top; });
  const visible = new Set(positioned.map(node => node.id));
  const edges = positioned.filter(node => node.parentId && node.parentId !== node.id && (node.parentId === 'current' || visible.has(node.parentId)))
    .map(node => ({ from: node.parentId!, to: node.id, relation: node.parentId === 'current' ? 'discovery' : 'gateway' }));
  return { width, height, hub, nodes: positioned, edges };
}

export function displayTime(value?: string | null) {
  if (!value) return '未上报';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '未上报' : date.toLocaleString();
}
