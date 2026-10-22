import { http } from './client';
import { API_CONFIG } from './config';
import { authenticatedFetch } from './authenticated-fetch';

export type RFileDevice = { deviceId: string; deviceName?: string; deviceType?: string; platform?: string;
  presence?: string; connectivity?: string; trustState?: string; deviceRole?: string;
  initiationStatus?: string; initiationBlockedReason?: string };
export type RFileService = { url: string; state: 'unchecked' | 'online' | 'offline' | 'error'; error: string | null; checked_at: string | null };
export type RFileStatus = { watch: RFileService; network: RFileService & { controller_registered: boolean; active_sessions: number | null };
  files: { enabled: boolean; max_file_bytes: number; reason: string | null }; devices: RFileDevice[]; config_error: string | null };
export type RFileEntry = { path: string; name: string; kind: 'directory' | 'file'; size: number | null; modified_at: string; readonly: boolean };
export type RFileListing = { path: string; entries: RFileEntry[]; skipped: number; max_file_bytes: number; writable: boolean };

export const rfileApi = {
  status: (signal?: AbortSignal) => http.get<RFileStatus>('/api/rfile/status', { signal }),
  refresh: (signal?: AbortSignal) => http.post<RFileStatus>('/api/rfile/refresh', undefined, { signal, timeout: 20000 }),
  list: (path: string, signal?: AbortSignal) => http.get<RFileListing>('/api/rfile/files', { params: { path }, signal, timeout: 20000 }),
  upload: (path: string, file: File, signal?: AbortSignal) => http.request<RFileEntry>('/api/rfile/upload', {
    method: 'PUT', params: { path, name: file.name }, body: file,
    headers: { 'Content-Type': 'application/octet-stream' }, timeout: 120000, signal,
  }),
  download: async (path: string, signal?: AbortSignal) => {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timeout = setTimeout(abort, 120000);
    try {
      const response = await authenticatedFetch(`${API_CONFIG.baseURL}/api/rfile/download?${new URLSearchParams({ path })}`, { signal: controller.signal });
      return await response.blob();
    } finally {
      clearTimeout(timeout); signal?.removeEventListener('abort', abort);
    }
  },
};
