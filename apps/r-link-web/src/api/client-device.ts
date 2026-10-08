import { invoke } from '@tauri-apps/api/core';
import type { DevicePlatform } from './devices';
import { getNativeFabricStatus, type NativeFabricStatus } from './fabric';

export type ClientDeviceInfo = {
  hostname: string | null;
  platform: DevicePlatform;
  runtime: 'desktop' | 'browser';
  netbird?: ClientNetbirdStatus | null;
  fabric?: NativeFabricStatus | null;
};

/** Public output of the installed local Agent's status command. */
export type ClientNetbirdStatus = {
  daemonStatus: string | null;
  management: { url: string | null; connected: boolean };
  signal: { connected: boolean };
  netbirdIp: string | null;
};

function publicNetbirdStatus(value: unknown): ClientNetbirdStatus | null {
  if (!value || typeof value !== 'object') return null;
  const item = value as Record<string, unknown>;
  const management = item.management && typeof item.management === 'object' ? item.management as Record<string, unknown> : {};
  const signal = item.signal && typeof item.signal === 'object' ? item.signal as Record<string, unknown> : {};
  const text = (value: unknown, limit: number) => typeof value === 'string' && value.length <= limit && !/[\u0000-\u001f\u007f]/.test(value) ? value : null;
  return { daemonStatus: text(item.daemonStatus, 64), management: { url: text(management.url, 2048), connected: management.connected === true }, signal: { connected: signal.connected === true }, netbirdIp: text(item.netbirdIp, 128) };
}

export function clientDeviceFallback(): ClientDeviceInfo {
  return { hostname: null, platform: 'unknown', runtime: typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window ? 'desktop' : 'browser' };
}

/** Read the client host locally; the configured API describes the service host. */
export async function getClientDeviceInfo(): Promise<ClientDeviceInfo> {
  const fallback = clientDeviceFallback();
  if (fallback.runtime === 'browser') return fallback;
  try {
    const [info, fabric] = await Promise.all([
      invoke<Pick<ClientDeviceInfo, 'hostname' | 'platform'> & { netbird?: unknown }>('desktop_device_info').catch(() => null),
      getNativeFabricStatus(),
    ]);
    if (!info) return { ...fallback, ...(fabric ? { fabric } : {}) };
    return { hostname: info.hostname, platform: info.platform, runtime: 'desktop', ...(info.netbird !== undefined ? { netbird: publicNetbirdStatus(info.netbird) } : {}), ...(fabric ? { fabric } : {}) };
  } catch {
    // Older desktop builds still show the operation endpoint without inventing a hostname.
    return fallback;
  }
}
