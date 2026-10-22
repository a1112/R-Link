import type { ConnectionStatus, Device, DevicePlatform, DeviceType } from '../api/devices';

export const deviceTypes: Record<DeviceType, string> = { computer: '电脑', server: '服务器', nas: 'NAS', mobile: '手机 / 平板', router: '路由器', iot: '物联网设备', other: '其他' };
export const devicePlatforms: Record<DevicePlatform, string> = { unknown: '未知平台', windows: 'Windows', linux: 'Linux', macos: 'macOS', android: 'Android', ios: 'iOS', other: '其他平台' };
export const connectionLabels: Record<ConnectionStatus, string> = { online: '在线', offline: '离线', unknown: '未知', removed: '已移除', revoked: '已撤销' };
export const sourceLabels = { manual: '手工登记', netbird: '组网节点', fabric: 'R-Link 组网', gateway: '通过网关' };
export function deviceAccessMode(device: Device) {
  if (device.connection_status === 'removed' || device.connection_status === 'revoked') return 'none';
  return device.access_mode ?? (device.source === 'netbird' || device.source === 'fabric' ? 'none' : 'ssh');
}
/** Accept only a plain DNS/IP host, never a URL or an authority with credentials. */
export function deviceWebUrl(device: Device): string | null {
  if (deviceAccessMode(device) !== 'web' || !['http', 'https'].includes(device.web_scheme ?? '') || !Number.isInteger(device.port) || device.port < 1 || device.port > 65535) return null;
  const host = device.host;
  if (!host || host.length > 253 || /[\s\/\\@?#\[\]%]/.test(host)) return null;
  const ipv6 = host.includes(':');
  if (ipv6 ? !/^[a-f\d:.]+$/i.test(host) : !host.split('.').every(label => /^[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?$/i.test(label))) return null;
  const address = `${device.web_scheme}://${ipv6 ? `[${host}]` : host}:${device.port}/`;
  try {
    const parsed = new URL(address);
    return parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash ? null : address;
  } catch { return null; }
}
export function officialInstallUrl(value: string): string | null {
  try { const url = new URL(value); return url.protocol === 'https:' && url.hostname === 'docs.netbird.io' && !url.username && !url.password ? url.href : null; }
  catch { return null; }
}
