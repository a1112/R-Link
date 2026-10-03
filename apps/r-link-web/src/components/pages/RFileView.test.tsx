import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RFileView } from './RFileView';
import { saveBlob } from '../../utils/download';
import type { RFileStatus } from '../../api/rfile';
import { setServiceKey } from '../../api/service-access';
vi.mock('../../utils/download', () => ({ saveBlob: vi.fn() }));

const state = (enabled = false): RFileStatus => ({ watch: { url: 'http://127.0.0.1:18080', state: 'online', error: null, checked_at: null },
  network: { url: 'http://127.0.0.1:18100', state: 'online', error: null, controller_registered: true, checked_at: null },
  devices: [{ deviceId: 'nas', deviceName: 'DS918+', platform: 'linux', presence: 'online', connectivity: 'relay' }],
  files: { enabled, reason: enabled ? null : '在服务端配置 R-File 访问凭据和一个共享目录后可浏览文件', max_file_bytes: 64 * 1024 * 1024 }, config_error: null });
const file = { name: 'actual.txt', path: 'actual.txt', kind: 'file', size: 5, modified_at: '', readonly: false };
const folder = { ...file, name: 'docs', path: 'docs', kind: 'directory', size: null };
const listing = (path = '', entries = [file, folder]) => ({ path, entries, skipped: 0, max_file_bytes: 64 * 1024 * 1024, writable: true });
let currentState = state();
let currentListing = listing();
let fetchMock: ReturnType<typeof vi.fn<(url: string, init?: RequestInit) => Promise<Response>>>;
beforeEach(() => {
  setServiceKey('operator-key');
  currentState = state(); currentListing = listing();
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const endpoint = new URL(url);
    if (endpoint.pathname.endsWith('/status') || endpoint.pathname.endsWith('/refresh')) return Response.json(currentState);
    if (endpoint.pathname.endsWith('/files')) return Response.json({ ...currentListing, path: endpoint.searchParams.get('path') || '' });
    if (endpoint.pathname.endsWith('/download')) return new Response('hello');
    if (endpoint.pathname.endsWith('/upload')) return Response.json(file, { status: 201 });
    return Response.json({ detail: 'unknown' }, { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

it('shows existing network devices and disabled filesystem capability without fictional addresses', async () => {
  render(<RFileView />);
  await screen.findByText('DS918+');
  expect(screen.getByText(/在服务端配置 R-File/)).toBeTruthy();
  expect(screen.getByText('http://127.0.0.1:18100')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'SSH' })).toBeNull();
  expect(screen.queryByRole('button', { name: '上传文件' })).toBeNull();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/files'))).toBe(false);
});

it('shows offline state and removes stale peers after refreshing', async () => {
  render(<RFileView />);
  await screen.findByText('DS918+');
  currentState = { ...state(), devices: [], network: { ...state().network, state: 'offline', error: '网络服务不可用', controller_registered: false } };
  fireEvent.click(screen.getByRole('button', { name: '刷新服务' }));
  await screen.findByText('网络服务不可用');
  expect(screen.queryByText('DS918+')).toBeNull();
});

it('navigates inside the configured root using only relative paths', async () => {
  currentState = state(true);
  render(<RFileView />);
  fireEvent.click(await screen.findByRole('button', { name: 'docs' }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('path=docs'))).toBe(true));
  fireEvent.click(screen.getByRole('button', { name: '返回上一级' }));
  await waitFor(() => expect((screen.getByRole('button', { name: '返回上一级' }) as HTMLButtonElement).disabled).toBe(true));
});

it('uploads selected bytes and downloads a blob through authenticated R-Link endpoints', async () => {
  currentState = state(true);
  render(<RFileView />);
  await screen.findByText('actual.txt');
  const upload = new File(['hello'], 'actual.txt');
  fireEvent.change(screen.getByLabelText('选择 R-File 上传文件'), { target: { files: [upload] } });
  await screen.findByText('已上传 actual.txt');
  const call = fetchMock.mock.calls.find(([url]) => String(url).includes('/upload'))!;
  expect(call[1]?.method).toBe('PUT');
  expect(call[1]?.body).toBe(upload);
  expect(call[1]?.redirect).toBe('error');
  expect(new Headers(call[1]?.headers).get('Authorization')).toBe('Bearer operator-key');
  fireEvent.click(screen.getByRole('button', { name: '下载 actual.txt' }));
  await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'actual.txt'));
  const download = fetchMock.mock.calls.find(([url]) => String(url).includes('/download'))!;
  expect(new Headers(download[1]?.headers).get('Authorization')).toBe('Bearer operator-key');
});

it('preserves server read-only restrictions and rejects oversize uploads before sending bytes', async () => {
  currentState = state(true); currentListing.writable = false;
  render(<RFileView />);
  await screen.findByText('actual.txt');
  expect((screen.getByRole('button', { name: '上传文件' }) as HTMLButtonElement).disabled).toBe(true);
  cleanup(); currentListing.writable = true;
  render(<RFileView />);
  await screen.findByText('actual.txt');
  const large = new File(['small'], 'large.txt');
  Object.defineProperty(large, 'size', { value: 64 * 1024 * 1024 + 1 });
  fireEvent.change(screen.getByLabelText('选择 R-File 上传文件'), { target: { files: [large] } });
  expect((await screen.findByRole('alert')).textContent).toContain('64 MiB');
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/upload'))).toBe(false);
});

it('cancels a pending transfer when the page unmounts', async () => {
  currentState = state(true);
  let transferSignal: AbortSignal | undefined;
  const standard = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
    if (String(url).includes('/download')) {
      transferSignal = init?.signal as AbortSignal;
      return new Promise<Response>((_, reject) => transferSignal!.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError')), { once: true }));
    }
    return standard(url, init);
  });
  const view = render(<RFileView />);
  fireEvent.click(await screen.findByRole('button', { name: '下载 actual.txt' }));
  await waitFor(() => expect(transferSignal).toBeTruthy());
  view.unmount();
  expect(transferSignal?.aborted).toBe(true);
});

it('removes stale file listings when a request fails', async () => {
  currentState = state(true);
  render(<RFileView />);
  await screen.findByText('actual.txt');
  const standard = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
    if (String(url).includes('/files')) return Response.json({ detail: 'R-File 拒绝访问该共享目录' }, { status: 403 });
    return standard(url, init);
  });
  fireEvent.click(screen.getByRole('button', { name: '刷新文件' }));
  await screen.findByRole('alert');
  expect(screen.queryByText('actual.txt')).toBeNull();
});

it('shows service check times next to cached service observations', async () => {
  currentState = { ...state(), watch: { ...state().watch, checked_at: '2026-10-03T06:00:00+00:00' },
    network: { ...state().network, checked_at: '2026-10-03T06:00:00+00:00' } } as RFileStatus;
  render(<RFileView />);
  await screen.findByText('DS918+');
  expect(screen.getAllByText(/最后检查/)).toHaveLength(2);
});
