import { invoke } from '@tauri-apps/api/core';
import { http } from './client';

export type FabricMode = 'vpn' | 'transport-test';
export type FabricPath = 'direct' | 'relay' | 'none';
export type FabricCapabilities = { enrollment: boolean; revocation: boolean; groups: boolean; p2p: boolean; relay: boolean; policies: boolean; networks: boolean; vpn?: boolean };
export type FabricStatus = { schema_version: 1; provider: 'rlink'; configured: boolean; control_url: string; peers: number; connected: number; config_version: number; mode: 'direct+relay'; mode_transport: FabricMode | 'unobserved'; capabilities: FabricCapabilities };
export type FabricGroup = { id: string; name: string };
export type FabricPeerPath = { peer_id: string; path: FabricPath; last_handshake: number | null; reported_at: number | null; rtt_ms?: number | null };
export type FabricPeer = { id: string; peer_id: string; name: string; os: string | null; ip: string | null; virtual_ip?: string | null; public_key: string; groups: FabricGroup[]; mode: FabricMode; connected: boolean; control_connected: boolean; relay_connected: boolean; tunnel_ready_reported: boolean; data_plane_confirmed: boolean; last_seen: number | null; paths: FabricPeerPath[] };
export type EnrollmentMetadata = { id: string; name: string; expires_at: number; groups: string[]; uses: 1; used: number; revoked?: boolean; created_at?: number };
export type Enrollment = EnrollmentMetadata & { enrollment_token: string };

export type NativeFabricPeer = { peer_id: string; ip: string | null; path: 'direct' | 'relay' | 'probing' | 'offline'; rtt_ms: number | null; last_handshake: number | null; handshake_age_seconds: number | null; rx_bytes: number; tx_bytes: number };
export type NativeFabricStatus = { schema_version: 1; provider: 'rlink-fabric'; device_id: string | null; name: string | null; control_url: string | null; control: { connected: boolean; last_success_at: number | null }; tun: { ready: boolean; name: string | null; ip: string | null }; peers: NativeFabricPeer[]; updated_at: number; mode: FabricMode; status_error?: 'stale' | 'not_running' | 'stopped' | 'invalid_status' | 'startup_failed' | null };

export function nativeFabricFresh(value?: NativeFabricStatus | null, now = Date.now() / 1000): boolean {
  return !!value && !value.status_error && Number.isFinite(value.updated_at) && now - value.updated_at <= 45 && value.updated_at <= now + 5;
}

/** The native command exposes a bounded public projection, never the Agent's private config. */
export async function getNativeFabricStatus(): Promise<NativeFabricStatus | null> {
  if (typeof window === 'undefined' || !('__TAURI_INTERNALS__' in window || '__TAURI__' in window)) return null;
  try {
    const status = await invoke<NativeFabricStatus | null>('desktop_fabric_info');
    if (!status || status.schema_version !== 1 || status.provider !== 'rlink-fabric' || !['vpn', 'transport-test'].includes(status.mode) || !Number.isFinite(status.updated_at) || !Array.isArray(status.peers)) return null;
    if (status.status_error != null && !['stale', 'not_running', 'stopped', 'invalid_status', 'startup_failed'].includes(status.status_error)) return null;
    return status;
  } catch { return null; }
}

const base = '/api/fabric';
export const fabricApi = {
  status: (signal?: AbortSignal) => http.get<FabricStatus>(`${base}/status`, { signal }),
  peers: (signal?: AbortSignal) => http.get<FabricPeer[]>(`${base}/peers`, { signal }),
  groups: (signal?: AbortSignal) => http.get<FabricGroup[]>(`${base}/groups`, { signal }),
  enrollments: async (signal?: AbortSignal) => (await http.get<{ enrollments: EnrollmentMetadata[] }>(`${base}/enrollments`, { signal })).enrollments,
  createEnrollment: (input: { name: string; groups: string[]; ttl_seconds: number }, signal?: AbortSignal) => http.post<Enrollment>(`${base}/enrollments`, { ...input, uses: 1 }, { signal }),
  revokeEnrollment: (id: string, signal?: AbortSignal) => http.post(`${base}/enrollments/${encodeURIComponent(id)}/revoke`, undefined, { signal }),
  revokePeer: (id: string, signal?: AbortSignal) => http.post(`${base}/peers/${encodeURIComponent(id)}/revoke`, undefined, { signal }),
};
