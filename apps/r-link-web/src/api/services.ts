import { http } from './client';
import { API_CONFIG } from './config';
import { authenticatedFetch } from './authenticated-fetch';

export interface Runtime { state: 'running' | 'stopped' | 'error'; pid: number | null; error: string | null }
export interface TunnelInput { name: string; server_host: string; server_port: number; local_host: string; local_port: number; remote_port: number; protocol: 'tcp' | 'udp'; token_env: string; autostart: boolean }
export interface Tunnel extends TunnelInput { id: string; runtime: Runtime }
export interface DomainInput { hostname: string; upstream_host: string; upstream_port: number; enabled: boolean; zone_id: string }
export interface Domain extends DomainInput { id: string }
export interface DomainStatus extends Runtime { pending_changes: boolean; dns_configured: boolean }
export interface DomainCheck { checked_at: string; addresses: string[]; tls_valid: boolean; certificate_expires_at: string | null; error: string | null }
export interface DNSRecord { id: string; type: string; name: string; content: string; ttl: number; proxied: boolean }
export interface Download { id: string; name: string; url: string; state: 'queued' | 'running' | 'paused' | 'failed' | 'completed' | 'cancelled'; downloaded: number; total: number | null; error: string | null }
export interface Capabilities { ready: boolean; frp: { available: boolean; reason: string | null }; https: { available: boolean; reason: string | null }; downloads: { available: boolean; max_bytes: number } }

export const servicesApi = {
  capabilities: (signal?: AbortSignal) => http.get<Capabilities>('/services', { signal }),
  tunnels: (signal?: AbortSignal) => http.get<Tunnel[]>('/tunnels', { signal }),
  saveTunnel: (data: TunnelInput, id?: string) => id ? http.put<Tunnel>(`/tunnels/${id}`, data) : http.post<Tunnel>('/tunnels', data),
  tunnelAction: (id: string, action: 'start' | 'stop') => http.post<Runtime>(`/tunnels/${id}/${action}`),
  deleteTunnel: (id: string) => http.delete(`/tunnels/${id}`),
  tunnelLogs: (id: string) => http.get<{ logs: string }>(`/tunnels/${id}/logs`),
  domains: (signal?: AbortSignal) => http.get<Domain[]>('/domains', { signal }),
  domainStatus: (signal?: AbortSignal) => http.get<DomainStatus>('/domains/service', { signal }),
  saveDomain: (data: DomainInput, id?: string) => id ? http.put<Domain>(`/domains/${id}`, data) : http.post<Domain>('/domains', data),
  deleteDomain: (id: string) => http.delete(`/domains/${id}`),
  domainAction: (action: 'apply' | 'stop') => http.post<DomainStatus>(`/domains/service/${action}`, undefined, { timeout: 45000 }),
  domainLogs: () => http.get<{ logs: string }>('/domains/service/logs'),
  checkDomain: (id: string) => http.post<DomainCheck>(`/domains/${id}/check`),
  dns: (id: string) => http.get<DNSRecord[]>(`/domains/${id}/dns`),
  createDNS: (id: string, data: { type: 'A' | 'AAAA' | 'CNAME'; content: string; ttl: number }) => http.post(`/domains/${id}/dns`, data),
  deleteDNS: (id: string, recordId: string) => http.delete(`/domains/${id}/dns/${recordId}`),
  downloads: (signal?: AbortSignal) => http.get<Download[]>('/downloads', { signal }),
  createDownload: (url: string, name: string) => http.post<Download>('/downloads', { url, name }),
  downloadAction: (id: string, action: 'pause' | 'resume' | 'cancel') => http.post<Download>(`/downloads/${id}/${action}`),
  deleteDownload: (id: string) => http.delete(`/downloads/${id}`),
  downloadFile: async (id: string) => (await authenticatedFetch(`${API_CONFIG.baseURL}/downloads/${id}/file`)).blob(),
};
