import type { Device, DeviceType } from '../../api/devices';
import type { RFileDevice, RFileStatus } from '../../api/rfile';
import type { ClientDeviceInfo } from '../../api/client-device';
import type { MeshPeer, MeshStatus } from '../../api/mesh';
import type { FabricPeer, FabricStatus } from '../../api/fabric';
import { connectionLabels, devicePlatforms, deviceTypes, sourceLabels } from '../device-presentation';

export type Presence = 'online' | 'offline' | 'unknown';
export type TopologyNode = {
  id: string; name: string; subtitle: string; type: DeviceType; source: 'inventory' | 'rfile' | 'client';
  sourceLabel: string; status: Presence; statusLabel: string; parentId: string | null;
  device?: Device; peer?: RFileDevice; client?: ClientDeviceInfo; clientMesh?: ClientMeshConfirmation; clientFabric?: ClientMeshConfirmation;
};
export type MeshSnapshot = { status: MeshStatus; peers: MeshPeer[] };
export type FabricSnapshot = { status: FabricStatus; peers: FabricPeer[] };
export type ClientMeshConfirmation = { confirmed: boolean; ip: string | null; managementUrl: string | null; expectedManagementUrl: string | null; reason: string };
export type Filters = { query: string; status: 'all' | Presence; type: string; source: string };
export const presenceLabels: Record<Presence, string> = { online: '在线', offline: '离线', unknown: '未知' };
const presence = (value?: string): Presence => value === 'online' || value === 'offline' ? value : 'unknown';

/** Canonical unicast addresses only; a hostname or service reachability is not an identity. */
export function virtualIp(value?: string | null): string | null {
  if (typeof value !== 'string' || value.length > 128 || /[\s%]/.test(value)) return null;
  const parts = value.split('/');
  if (parts.length > 2 || (parts.length === 2 && !/^\d{1,3}$/.test(parts[1]))) return null;
  const address = parts[0];
  if (address.includes(':')) {
    if (parts.length === 2 && (Number(parts[1]) < 1 || Number(parts[1]) > 128)) return null;
    try {
      const canonical = new URL(`http://[${address}]/`).hostname.replace(/^\[|\]$/g, '');
      const first = parseInt(canonical.split(':')[0], 16);
      // Global unicast and ULA exclude loopback, link-local and multicast identities.
      return (first >= 0x2000 && first <= 0x3fff) || (first >= 0xfc00 && first <= 0xfdff) ? canonical : null;
    } catch { return null; }
  }
  if (parts.length === 2 && (Number(parts[1]) < 1 || Number(parts[1]) > 32)) return null;
  const octets = address.split('.');
  if (octets.length !== 4 || octets.some(value => !/^\d{1,3}$/.test(value) || Number(value) > 255 || String(Number(value)) !== value)) return null;
  const numbers = octets.map(Number);
  if (numbers[0] === 0 || numbers[0] === 127 || numbers[0] >= 224 || (numbers[0] === 169 && numbers[1] === 254)) return null;
  return numbers.join('.');
}

function controlplane(value?: string | null): string | null {
  if (!value || value.length > 2048 || /[\s\\]/.test(value)) return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password && !url.hash && !url.search ? url.toString() : null;
  } catch { return null; }
}

export function confirmClientMesh(client?: ClientDeviceInfo, mesh?: MeshSnapshot | null): ClientMeshConfirmation {
  const local = client?.netbird;
  const ip = virtualIp(local?.netbirdIp);
  const managementUrl = controlplane(local?.management.url);
  const expectedManagementUrl = controlplane(mesh?.status.management_url);
  const result = { confirmed: false, ip, managementUrl, expectedManagementUrl, reason: '未读取到本机 NetBird Agent 状态' };
  if (client?.runtime !== 'desktop' || !local) return result;
  if (local.daemonStatus !== 'Connected' || !local.management.connected || !local.signal.connected) return { ...result, reason: '本机 NetBird Agent 尚未完整连接管理端与信令端' };
  if (!ip) return { ...result, reason: '本机 Agent 尚未报告有效虚拟 IP' };
  if (!mesh?.status.configured || !mesh.status.reachable || !expectedManagementUrl) return { ...result, reason: '当前服务的 NetBird 控制面暂不可用，入网身份待确认' };
  if (!managementUrl || managementUrl !== expectedManagementUrl) return { ...result, reason: '本机 Agent 连接的控制面与当前服务不一致' };
  return { ...result, confirmed: true, reason: '已确认本机 Agent 连接当前控制面；不代表节点之间 P2P 或业务端口可达' };
}

export function confirmClientFabric(client?: ClientDeviceInfo, fabric?: FabricSnapshot | null): ClientMeshConfirmation {
  const local = client?.fabric;
  const ip = virtualIp(local?.tun.ip);
  const managementUrl = controlplane(local?.control_url);
  const expectedManagementUrl = controlplane(fabric?.status.control_url);
  const result = { confirmed: false, ip, managementUrl, expectedManagementUrl, reason: '未读取到本机 R-Link Agent 状态' };
  if (client?.runtime !== 'desktop' || !local) return result;
  const now = Date.now() / 1000;
  if (local.status_error || now - local.updated_at > 45 || local.updated_at > now + 5) return { ...result, reason: '本机 Agent 状态已过期或服务未运行' };
  if (local.mode !== 'vpn') return { ...result, reason: '自研 Agent 正在测试中转与打洞传输，尚未建立系统 VPN' };
  if (!local.control.connected || !local.tun.ready || !ip) return { ...result, reason: '自研 Agent 控制连接、系统 TUN 或虚拟 IP 尚未就绪' };
  if (!fabric?.status.configured || fabric.status.provider !== 'rlink' || !managementUrl || managementUrl !== expectedManagementUrl) return { ...result, reason: '自研控制面不可用或与本机 Agent 不一致' };
  const peer = fabric.peers.find(peer => peer.id === local.device_id || peer.peer_id === local.device_id);
  const currentPeer = peer && peer.mode === 'vpn' && peer.connected && peer.control_connected && peer.tunnel_ready_reported && peer.data_plane_confirmed && !!peer.last_seen && now - peer.last_seen <= 45 && peer.last_seen <= now + 5 && virtualIp(peer.ip || peer.virtual_ip) === ip;
  const handshake = local.peers.some(peer => ['direct', 'relay'].includes(peer.path) && !!peer.last_handshake && now - peer.last_handshake <= 180 && peer.last_handshake <= now + 5);
  if (!currentPeer || !handshake) return { ...result, reason: '登记心跳或近期真实 WireGuard 握手尚未确认；路径探测成功不能替代 VPN 数据面' };
  return { ...result, confirmed: true, reason: '自研 Agent 系统 TUN 与近期 WireGuard 握手已确认；单项业务端口仍需实际测试' };
}

export function makeNodes(devices: Device[], rfile: RFileStatus | null, client?: ClientDeviceInfo, mesh?: MeshSnapshot | null, fabric?: FabricSnapshot | null): TopologyNode[] {
  const clientMesh = confirmClientMesh(client, mesh);
  const clientFabric = confirmClientFabric(client, fabric);
  const candidates = clientMesh.confirmed ? devices.filter(device => device.source === 'netbird' && device.connection_status === 'online' && !device.gateway_id && !!device.peer_id && virtualIp(device.host) === clientMesh.ip
    && mesh?.peers.some(peer => peer.id === device.peer_id && peer.connected && virtualIp(peer.ip) === clientMesh.ip)) : [];
  // An ambiguous inventory keeps every record; only one proven direct peer may be merged.
  const localNetbird = candidates.length === 1 ? candidates[0] : undefined;
  const fabricCandidates = clientFabric.confirmed ? devices.filter(device => {
    if (device.source !== 'fabric' || device.gateway_id || device.connection_status !== 'online' || device.peer_id !== client?.fabric?.device_id || virtualIp(device.host) !== clientFabric.ip || !device.provider_url) return false;
    try {
      const provider = new URL(device.provider_url);
      if (provider.hash !== '#rlink-fabric') return false;
      provider.hash = '';
      return controlplane(provider.toString()) === clientFabric.expectedManagementUrl;
    } catch { return false; }
  }) : [];
  const localFabric = fabricCandidates.length === 1 ? fabricCandidates[0] : undefined;
  const localDevice = localFabric || localNetbird;
  const merged = new Set([localFabric?.id, localNetbird?.id].filter(Boolean));
  return [
    ...(client ? [{
      id: 'client:current', name: '本电脑', subtitle: client.hostname || (client.runtime === 'desktop' ? '当前桌面客户端' : '当前浏览器'),
      type: 'computer' as const, source: 'client' as const, sourceLabel: '当前操作端',
      status: clientFabric.confirmed || clientMesh.confirmed ? 'online' as const : 'unknown' as const, statusLabel: clientFabric.confirmed ? '自研 VPN 握手已确认' : clientMesh.confirmed ? '已入网 · 管理端在线' : client?.fabric?.mode === 'transport-test' ? '自研传输测试 · 非 VPN' : '组网未确认', parentId: 'current', client, clientMesh, ...(client?.fabric ? { clientFabric } : {}), ...(localDevice ? { device: localDevice } : {}),
    }] : []),
    ...devices.filter(device => !merged.has(device.id)).map((device): TopologyNode => ({
      id: `device:${device.id}`, name: device.name, type: device.device_type ?? 'other', source: 'inventory',
      subtitle: `${devicePlatforms[device.platform ?? 'unknown']} · ${deviceTypes[device.device_type ?? 'other']}`,
      sourceLabel: sourceLabels[device.source ?? 'manual'], status: presence(device.connection_status),
      statusLabel: connectionLabels[device.connection_status ?? 'unknown'],
      parentId: device.source === 'gateway' ? (device.gateway_id ? merged.has(device.gateway_id) ? 'client:current' : `device:${device.gateway_id}` : null) : 'current', device,
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
    && [node.name, node.client?.hostname, node.clientMesh?.ip, node.clientMesh?.managementUrl, node.device?.name, node.peer?.deviceName, node.peer?.deviceId, node.subtitle, node.device?.host, ...(node.device?.tags ?? []), ...(node.device?.mesh_groups ?? []).map(group => group.name)]
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
    .map(node => ({ from: node.parentId!, to: node.id, relation: node.source === 'client' ? 'client' : node.parentId === 'current' ? 'discovery' : 'gateway' }));
  return { width, height, hub, nodes: positioned, edges };
}

export function displayTime(value?: string | null) {
  if (!value) return '未上报';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '未上报' : date.toLocaleString();
}
