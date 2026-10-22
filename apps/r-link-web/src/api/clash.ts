import { http } from './client';

export interface ClashSettings {
  controller_url: string;
  has_secret: boolean;
}

export interface ClashSettingsInput {
  controller_url: string;
  /** A blank secret is intentionally omitted so the server keeps its current value. */
  secret?: string;
  clear_secret?: boolean;
}

export type ClashManagedState = 'running' | 'stopped' | 'starting' | 'stopping' | 'error' | string;

export interface ClashManagedStatus {
  available: boolean;
  state: ClashManagedState;
  pid: number | null;
  error: string | null;
  profile_id: string | null;
}

export interface ClashStatus {
  configured: boolean;
  connected: boolean;
  controller_url: string;
  version: string | null;
  error: string | null;
  managed: ClashManagedStatus;
}

export type ClashMode = 'rule' | 'global' | 'direct';
export type ClashLogLevel = 'silent' | 'error' | 'warning' | 'info' | 'debug';

export interface ClashConfigs {
  mode: ClashMode | null;
  log_level: ClashLogLevel | null;
  mixed_port: number;
  port: number;
  socks_port: number;
  allow_lan: boolean;
  tun_enabled: boolean;
}

export interface ClashProxyHistory {
  time: string;
  delay: number;
}

export interface ClashProxy {
  name: string;
  type: string;
  now?: string;
  all?: string[];
  history?: ClashProxyHistory[];
  alive?: boolean;
}

export interface ClashProxiesResponse {
  proxies: Record<string, ClashProxy>;
}

export interface ClashRule {
  type: string;
  payload: string;
  proxy: string;
}

export interface ClashRulesResponse {
  rules: ClashRule[];
}

export interface ClashConnectionMetadata {
  network: string;
  type: string;
  sourceIP: string;
  sourcePort: number | string;
  destinationIP: string;
  destinationPort: number | string;
  host: string;
  process?: string | null;
}

export interface ClashConnection {
  id: string;
  start: string;
  upload: number;
  download: number;
  chains: string[];
  rule: string;
  metadata: ClashConnectionMetadata;
  process?: string | null;
}

export interface ClashConnectionsResponse {
  downloadTotal: number;
  uploadTotal: number;
  connections: ClashConnection[];
}

export interface ClashSubscriptionInfo {
  Upload: number | string;
  Download: number | string;
  Total: number | string;
  Expire: number | string;
}

export interface ClashProvider {
  name: string;
  type: string;
  vehicleType: string;
  updatedAt?: string;
  subscriptionInfo?: ClashSubscriptionInfo;
  proxies?: ClashProxy[];
}

export interface ClashProvidersResponse {
  providers: Record<string, ClashProvider>;
}

export interface ClashProfile {
  id: string;
  name: string;
  active: boolean;
  updated_at: string;
}

export interface ClashProfileInput {
  name: string;
  content: string;
}

const resource = (value: string): string => encodeURIComponent(value);

export const clashApi = {
  settings: (signal?: AbortSignal) => http.get<ClashSettings>('/api/clash/settings', { signal }),
  saveSettings: (input: ClashSettingsInput) => http.put<ClashSettings>('/api/clash/settings', input),
  status: (signal?: AbortSignal) => http.get<ClashStatus>('/api/clash/status', { signal }),
  configs: (signal?: AbortSignal) => http.get<ClashConfigs>('/api/clash/configs', { signal }),
  updateConfigs: (input: Partial<Pick<ClashConfigs, 'mode' | 'log_level'>>) => http.patch<ClashConfigs>('/api/clash/configs', input),
  proxies: (signal?: AbortSignal) => http.get<ClashProxiesResponse>('/api/clash/proxies', { signal }),
  selectProxy: (group: string, name: string) => http.put<ClashProxy>(`/api/clash/proxies/${resource(group)}`, { name }),
  proxyDelay: (group: string, timeout = 5000, signal?: AbortSignal) => http.get<{ delay: number }>(`/api/clash/proxies/${resource(group)}/delay`, { params: { timeout }, signal }),
  rules: (signal?: AbortSignal) => http.get<ClashRulesResponse>('/api/clash/rules', { signal }),
  connections: (signal?: AbortSignal) => http.get<ClashConnectionsResponse>('/api/clash/connections', { signal }),
  closeConnection: (id: string, sourceId?: string) => http.delete(`/api/clash/connections/${resource(id)}`, sourceId ? { params: { source_id: sourceId } } : undefined),
  closeAllConnections: (sourceId?: string) => sourceId ? http.delete('/api/clash/connections', { params: { source_id: sourceId } }) : http.delete('/api/clash/connections'),
  providers: (signal?: AbortSignal) => http.get<ClashProvidersResponse>('/api/clash/providers/proxies', { signal }),
  refreshProvider: (name: string) => http.put<ClashProvider>(`/api/clash/providers/proxies/${resource(name)}`),
  profiles: (signal?: AbortSignal) => http.get<ClashProfile[]>('/api/clash/profiles', { signal }),
  createProfile: (input: ClashProfileInput) => http.post<ClashProfile>('/api/clash/profiles', input),
  deleteProfile: (id: string) => http.delete(`/api/clash/profiles/${resource(id)}`),
  startManaged: (profileId: string) => http.post<ClashManagedStatus>('/api/clash/managed/start', { profile_id: profileId }),
  stopManaged: () => http.post<ClashManagedStatus>('/api/clash/managed/stop'),
};

export default clashApi;
