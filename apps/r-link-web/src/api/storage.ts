import { http } from './client';
import { API_CONFIG } from './config';
import { authenticatedFetch } from './authenticated-fetch';

export type StorageEntry = { name: string; path: string; kind: 'directory' | 'file'; size: number | null; modified_at: string };
export type StorageListing = { path: string; entries: StorageEntry[]; skipped: number; max_file_bytes: number };
export const storageApi = {
  list: (path: string, signal?: AbortSignal) => http.get<StorageListing>('/api/storage', { params: { path }, signal }),
  mkdir: (path: string, name: string) => http.post<StorageEntry>('/api/storage/directory', { path, name }),
  rename: (path: string, name: string) => http.post<StorageEntry>('/api/storage/rename', { path, name }),
  remove: (path: string) => http.delete<void>('/api/storage', { params: { path } }),
  upload: (path: string, file: File, signal?: AbortSignal) => http.request<StorageEntry>('/api/storage/upload', {
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
      const response = await authenticatedFetch(`${API_CONFIG.baseURL}/api/storage/download?${new URLSearchParams({ path })}`, { signal: controller.signal });
      return await response.blob();
    } finally {
      clearTimeout(timeout); signal?.removeEventListener('abort', abort);
    }
  },
};
