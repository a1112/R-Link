import { http } from './client';
export type DeviceType = 'computer' | 'server' | 'nas' | 'mobile' | 'router' | 'iot' | 'other';
export type DevicePlatform = 'unknown' | 'windows' | 'linux' | 'macos' | 'android' | 'ios' | 'other';
export type ConnectionStatus = 'online' | 'offline' | 'unknown' | 'removed' | 'revoked';
export type DeviceInput = {
  name: string; host: string; port: number; username: string;
  device_type?: DeviceType; platform?: DevicePlatform; tags?: string[]; notes?: string;
  access_mode?: 'ssh' | 'web' | 'none'; web_scheme?: 'http' | 'https'; gateway_id?: string | null;
};
export type Device = DeviceInput & {
  id: string; revision: number; status: 'unchecked' | 'reachable' | 'unreachable'; checked_at: string | null; latency_ms: number | null;
  source?: 'manual' | 'netbird' | 'fabric' | 'gateway'; peer_id?: string | null; provider_url?: string | null; connection_status?: ConnectionStatus;
  last_seen?: string | null; synced_at?: string | null; mesh_groups?: { id: string; name: string }[]; gateway_status?: ConnectionStatus | null;
};
export type DeviceInventory = { version: 1 | 2; devices: DeviceInput[] };
export type DeviceManagementStatus = { configured: boolean; syncing: boolean; interval_seconds: number; stale_seconds: number; last_synced_at: string | null; last_error: string | null };
export type DeviceSyncResult = { added: number; updated: number; missing: number; conflicts: { peer_id: string; device_id: string; host: string; port: number; reason: 'endpoint_already_registered' }[]; synced_at: string };
export type DeviceOnboarding = { configured: boolean; management_url: string | null; platforms: { id: string; name: string; url: string }[]; instructions: string[] };
const path = (id: string) => `/api/devices/${encodeURIComponent(id)}`;
export const devicesApi = {
  list: (signal?: AbortSignal) => http.get<Device[]>('/api/devices', { signal }),
  save: (value: DeviceInput, id?: string, signal?: AbortSignal) => id ? http.put<Device>(path(id), value, { signal }) : http.post<Device>('/api/devices', value, { signal }),
  remove: (id: string, signal?: AbortSignal) => http.delete<void>(path(id), { signal }),
  probe: (id: string, signal?: AbortSignal) => http.post<Device>(`${path(id)}/probe`, undefined, { signal }),
  export: (version: 1 | 2 = 1, signal?: AbortSignal) => http.get<DeviceInventory>(`/api/devices/export${version === 2 ? '?version=2' : ''}`, { signal }),
  import: (data: unknown, signal?: AbortSignal) => http.post<{ added: number; skipped: number }>('/api/devices/import', data, { signal }),
  managementStatus: (signal?: AbortSignal) => http.get<DeviceManagementStatus>('/api/devices/management-status', { signal }),
  sync: (signal?: AbortSignal) => http.post<DeviceSyncResult>('/api/devices/sync', undefined, { signal }),
  onboarding: (signal?: AbortSignal) => http.get<DeviceOnboarding>('/api/devices/onboarding', { signal }),
  link: (id: string, peerId: string, signal?: AbortSignal) => http.post<Device>(`${path(id)}/link`, { peer_id: peerId }, { signal }),
  revoke: (id: string, signal?: AbortSignal) => http.post<Device>(`${path(id)}/revoke`, undefined, { signal }),
};
