import { http } from './client';

export interface MeshStatus { configured: boolean; reachable: boolean; management_url?: string; peers: number; connected: number; reason: string | null }
export interface MeshPeer { id: string; name: string; ip: string | null; ipv6: string | null; connected: boolean; last_seen: string | null; os: string | null; groups: { id: string; name: string }[] }
export interface MeshGroup { id: string; name: string; peers_count?: number; peers?: { id: string; name: string }[]; resources?: { id: string; type: string }[] }
export interface MeshKey { id: string | number; name: string; type: string; valid: boolean; revoked: boolean; expires: string; used_times: number; auto_groups: string[]; key?: string }
export interface MeshPolicy { id: string; name: string; description?: string; enabled: boolean; source_posture_checks?: string[]; rules: { sources?: { id: string; name: string }[]; destinations?: { id: string; name: string }[]; protocol?: string; ports?: string[]; port_ranges?: unknown[]; authorized_groups?: object; sourceResource?: object; destinationResource?: object; bidirectional?: boolean }[] }
export interface MeshNetwork { id: string; name: string; description: string; routing_peers_count?: number }
export interface MeshResource { id: string; name: string; address: string; enabled: boolean; groups: { id: string; name: string }[]; description: string }
export interface MeshRouter { id: string; peer?: string; peer_groups?: string[]; metric: number; masquerade: boolean; enabled: boolean }
export interface PolicyInput { name: string; source_group: string; destination_group: string; protocol: 'all' | 'tcp' | 'udp' | 'icmp'; ports: number[]; enabled: boolean; bidirectional: boolean }
export interface ResourceInput { name: string; address: string; description: string; enabled: boolean; groups: string[] }
export interface RouterInput { peer: string | null; peer_groups: string[]; metric: number; masquerade: boolean; enabled: boolean }

const base = '/api/mesh';
export const meshApi = {
  status: (signal?: AbortSignal) => http.get<MeshStatus>(base + '/status', { signal }),
  peers: (signal?: AbortSignal) => http.get<MeshPeer[]>(base + '/peers', { signal }),
  renamePeer: (id: string, name: string) => http.put<MeshPeer>(`${base}/peers/${id}`, { name }),
  deletePeer: (id: string) => http.delete(`${base}/peers/${id}`),
  groups: (signal?: AbortSignal) => http.get<MeshGroup[]>(base + '/groups', { signal }),
  saveGroup: (name: string, peers: string[], id?: string) => id ? http.put<MeshGroup>(`${base}/groups/${id}`, { name, peers }) : http.post<MeshGroup>(base + '/groups', { name, peers }),
  deleteGroup: (id: string) => http.delete(`${base}/groups/${id}`),
  keys: (signal?: AbortSignal) => http.get<MeshKey[]>(base + '/setup-keys', { signal }),
  createKey: (name: string, group: string, reusable: boolean) => http.post<MeshKey>(base + '/setup-keys', {
    name, type: reusable ? 'reusable' : 'one-off', expires_in: 86400, auto_groups: [group], usage_limit: reusable ? 10 : 1, ephemeral: false,
  }),
  revokeKey: (id: string | number) => http.post(`${base}/setup-keys/${id}/revoke`),
  deleteKey: (id: string | number) => http.delete(`${base}/setup-keys/${id}`),
  policies: (signal?: AbortSignal) => http.get<MeshPolicy[]>(base + '/policies', { signal }),
  savePolicy: (input: PolicyInput, id?: string) => id ? http.put<MeshPolicy>(`${base}/policies/${id}`, input) : http.post<MeshPolicy>(base + '/policies', input),
  deletePolicy: (id: string) => http.delete(`${base}/policies/${id}`),
  networks: (signal?: AbortSignal) => http.get<MeshNetwork[]>(base + '/networks', { signal }),
  saveNetwork: (name: string, description: string, id?: string) => id ? http.put<MeshNetwork>(`${base}/networks/${id}`, { name, description }) : http.post<MeshNetwork>(base + '/networks', { name, description }),
  deleteNetwork: (id: string) => http.delete(`${base}/networks/${id}`),
  resources: (id: string, signal?: AbortSignal) => http.get<MeshResource[]>(`${base}/networks/${id}/resources`, { signal }),
  saveResource: (id: string, input: ResourceInput, resourceId?: string) => resourceId ? http.put<MeshResource>(`${base}/networks/${id}/resources/${resourceId}`, input) : http.post<MeshResource>(`${base}/networks/${id}/resources`, input),
  deleteResource: (id: string, resourceId: string) => http.delete(`${base}/networks/${id}/resources/${resourceId}`),
  routers: (id: string, signal?: AbortSignal) => http.get<MeshRouter[]>(`${base}/networks/${id}/routers`, { signal }),
  saveRouter: (id: string, input: RouterInput, routerId?: string) => routerId ? http.put<MeshRouter>(`${base}/networks/${id}/routers/${routerId}`, input) : http.post<MeshRouter>(`${base}/networks/${id}/routers`, input),
  deleteRouter: (id: string, routerId: string) => http.delete(`${base}/networks/${id}/routers/${routerId}`),
};
