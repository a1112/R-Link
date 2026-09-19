import { http } from './client';
export type DeviceInput = { name: string; host: string; port: number; username: string };
export type Device = DeviceInput & { id: string; revision: number; status: 'unchecked' | 'reachable' | 'unreachable'; checked_at: string | null; latency_ms: number | null };
export const devicesApi = {
  list: (signal?: AbortSignal) => http.get<Device[]>('/api/devices', { signal }),
  save: (value: DeviceInput, id?: string) => id ? http.put<Device>(`/api/devices/${encodeURIComponent(id)}`, value) : http.post<Device>('/api/devices', value),
  remove: (id: string) => http.delete<void>(`/api/devices/${encodeURIComponent(id)}`),
  probe: (id: string) => http.post<Device>(`/api/devices/${encodeURIComponent(id)}/probe`),
};
