import { http } from './client';

export type QoSPriority = 0 | 3 | 7;

export interface QoSPolicy {
  id: string;
  label: string;
  device_id: string | null;
  ip: string;
  enabled: boolean;
  upload_mbps: number | null;
  download_mbps: number | null;
  guaranteed_upload_mbps: number;
  guaranteed_download_mbps: number;
  priority: QoSPriority;
}

export type Policy = QoSPolicy;

export interface QoSConfig {
  interface: string;
  upload_mbps: number;
  download_mbps: number;
  policies: QoSPolicy[];
}

export interface QoSCapabilities {
  available: boolean;
  platform: string;
  reason: string | null;
  interfaces: Array<{ name: string }>;
  backend: 'linux-tc-htb-ifb';
}

export interface QoSRevision {
  revision: number;
  config: QoSConfig;
}

export type QoSState = 'inactive' | 'pending' | 'active' | 'error' | 'unavailable';

export interface QoSStatus {
  capabilities: QoSCapabilities;
  desired: QoSRevision;
  applied: QoSRevision | null;
  /** Revision of an applied/partial install whose cleanup still needs confirmation. */
  cleanup_revision?: number | null;
  state: QoSState;
  error: string | null;
  statistics?: unknown;
}

const IPV4_PART = /^(?:0|[1-9]\d{0,2})$/;
const IPV6_PART = /^[0-9a-fA-F]{1,4}$/;

function isUnicastIpv4(value: string): boolean {
  const parts = value.split('.');
  if (parts.length !== 4 || parts.some(part => !IPV4_PART.test(part))) return false;
  const numbers = parts.map(Number);
  if (numbers.some(part => part > 255)) return false;
  const first = numbers[0];
  if (first === 0 || first === 127 || first >= 224) return false;
  if (numbers.every(part => part === 255)) return false;
  return true;
}

function isUnicastIpv6(value: string): boolean {
  let input = value;
  const mapped = input.match(/^(.*:)([0-9]+(?:\.[0-9]+){3})$/);
  if (mapped) {
    const mappedParts = mapped[2].split('.');
    if (mappedParts.length !== 4 || mappedParts.some(part => !/^\d+$/.test(part) || Number(part) > 255)) return false;
    if (!isUnicastIpv4(mapped[2])) return false;
    // Parse IPv4-embedded IPv6 in the same form as an IPv6 literal. This
    // also lets the IPv4 checks reject mapped loopback/unspecified addresses.
    const first = ((Number(mappedParts[0]) << 8) | Number(mappedParts[1])).toString(16);
    const second = ((Number(mappedParts[2]) << 8) | Number(mappedParts[3])).toString(16);
    input = `${mapped[1]}${first}:${second}`;
  }
  if (!input.includes(':') || !/^[0-9a-fA-F:]+$/.test(input) || input.includes(':::')) return false;
  const sections = input.split('::');
  if (sections.length > 2) return false;
  const left = sections[0] ? sections[0].split(':') : [];
  const right = sections.length === 2 && sections[1] ? sections[1].split(':') : [];
  if (left.some(part => !IPV6_PART.test(part)) || right.some(part => !IPV6_PART.test(part))) return false;
  const partCount = left.length + right.length;
  if (sections.length === 1 ? partCount !== 8 : partCount >= 8) return false;
  const expanded = left.concat(Array(8 - partCount).fill('0'), right).map(part => Number.parseInt(part, 16));
  if (expanded.every(part => part === 0)) return false;
  if (expanded.slice(0, 7).every(part => part === 0) && expanded[7] === 1) return false;
  if (expanded.slice(0, 5).every(part => part === 0) && expanded[5] === 0xffff) {
    const mappedIpv4 = [expanded[6] >> 8, expanded[6] & 0xff, expanded[7] >> 8, expanded[7] & 0xff].join('.');
    if (!isUnicastIpv4(mappedIpv4)) return false;
  }
  if ((expanded[0] & 0xff00) === 0xff00) return false;
  return true;
}

/** Returns true only for a literal, non-multicast, non-unspecified device IP. */
export function isLiteralUnicastIp(value: string): boolean {
  const input = value.trim();
  if (!input || input.includes('/') || input.includes('%')) return false;
  return input.includes(':') ? isUnicastIpv6(input) : isUnicastIpv4(input);
}

export function cloneQoSConfig(config: QoSConfig): QoSConfig {
  return {
    interface: config.interface,
    upload_mbps: config.upload_mbps,
    download_mbps: config.download_mbps,
    policies: config.policies.map(policy => ({ ...policy })),
  };
}

export function normalizeQoSConfig(config: QoSConfig): QoSConfig {
  return {
    ...cloneQoSConfig(config),
    interface: config.interface.trim(),
    policies: config.policies.map(policy => ({
      ...policy,
      id: policy.id.trim(),
      label: policy.label.trim(),
      ip: policy.ip.trim(),
      device_id: policy.device_id?.trim() || null,
    })),
  };
}

export function createQoSPolicy(id: string, label = '新设备'): QoSPolicy {
  return {
    id,
    label,
    device_id: null,
    ip: '',
    enabled: true,
    upload_mbps: null,
    download_mbps: null,
    guaranteed_upload_mbps: 0.1,
    guaranteed_download_mbps: 0.1,
    priority: 3,
  };
}

/** Returns a user-facing validation message, or null for a valid configuration. */
export function validateQoSConfig(config: QoSConfig): string | null {
  if (!Number.isFinite(config.upload_mbps) || config.upload_mbps < 1 || config.upload_mbps > 100000) return '总上传上限必须在 1 到 100000 Mbps 之间。';
  if (!Number.isFinite(config.download_mbps) || config.download_mbps < 1 || config.download_mbps > 100000) return '总下载上限必须在 1 到 100000 Mbps 之间。';
  if (!Array.isArray(config.policies) || config.policies.length > 64) return '设备策略最多保存 64 条。';

  const ids = new Set<string>();
  const ips = new Set<string>();
  let guaranteedUpload = 0;
  let guaranteedDownload = 0;
  for (const policy of config.policies) {
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(policy.id) || ids.has(policy.id)) return '每条策略都需要唯一的有效标识。';
    ids.add(policy.id);
    if (!policy.label.trim() || policy.label.trim().length > 80) return '策略名称需要为 1 到 80 个字符。';
    if (!isLiteralUnicastIp(policy.ip) || ips.has(policy.ip.trim())) return '每条策略需要唯一的设备单播 IP 地址。';
    ips.add(policy.ip.trim());
    if (policy.upload_mbps !== null && (!Number.isFinite(policy.upload_mbps) || policy.upload_mbps < 0.001 || policy.upload_mbps > 100000)) return '设备上传上限必须在 0.001 到 100000 Mbps 之间，或留空使用总上限。';
    if (policy.download_mbps !== null && (!Number.isFinite(policy.download_mbps) || policy.download_mbps < 0.001 || policy.download_mbps > 100000)) return '设备下载上限必须在 0.001 到 100000 Mbps 之间，或留空使用总上限。';
    if (!Number.isFinite(policy.guaranteed_upload_mbps) || policy.guaranteed_upload_mbps < 0.001 || policy.guaranteed_upload_mbps > 100000) return '上传保障带宽需要在 0.001 到 100000 Mbps 之间。';
    if (!Number.isFinite(policy.guaranteed_download_mbps) || policy.guaranteed_download_mbps < 0.001 || policy.guaranteed_download_mbps > 100000) return '下载保障带宽需要在 0.001 到 100000 Mbps 之间。';
    if (policy.priority !== 0 && policy.priority !== 3 && policy.priority !== 7) return '策略优先级无效。';
    if (policy.enabled) {
      const uploadMax = policy.upload_mbps ?? config.upload_mbps;
      const downloadMax = policy.download_mbps ?? config.download_mbps;
      if (uploadMax > config.upload_mbps || uploadMax < policy.guaranteed_upload_mbps) return '启用策略的上传速率必须满足保障带宽不超过设备上限和总量。';
      if (downloadMax > config.download_mbps || downloadMax < policy.guaranteed_download_mbps) return '启用策略的下载速率必须满足保障带宽不超过设备上限和总量。';
      guaranteedUpload += policy.guaranteed_upload_mbps;
      guaranteedDownload += policy.guaranteed_download_mbps;
    }
  }
  if (guaranteedUpload + 0.001 > config.upload_mbps + 1e-9) return '上传保障带宽总和超过总量。';
  if (guaranteedDownload + 0.001 > config.download_mbps + 1e-9) return '下载保障带宽总和超过总量。';
  return null;
}

export const qosApi = {
  status(signal?: AbortSignal) {
    return http.get<QoSStatus>('/api/qos/status', { signal });
  },
  saveConfig(expectedRevision: number, config: QoSConfig) {
    return http.put<QoSStatus>('/api/qos/config', {
      expected_revision: expectedRevision,
      config,
    });
  },
  apply(expectedRevision: number) {
    return http.post<QoSStatus>('/api/qos/apply', {
      expected_revision: expectedRevision,
    });
  },
  removeApplied(expectedRevision: number) {
    return http.delete<QoSStatus>('/api/qos/applied', {
      params: { expected_revision: expectedRevision },
    });
  },
};

