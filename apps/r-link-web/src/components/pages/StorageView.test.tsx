import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { storageApi, type StorageEntry, type StorageListing } from '../../api/storage';
import { saveBlob } from '../../utils/download';
vi.mock('../../api/storage', () => ({ storageApi: { list: vi.fn(), mkdir: vi.fn(), rename: vi.fn(), remove: vi.fn(), upload: vi.fn(), download: vi.fn() } }));
vi.mock('../../utils/download', () => ({ saveBlob: vi.fn() }));
import { StorageView } from './StorageView';
const file: StorageEntry = { name: 'actual.txt', path: 'actual.txt', kind: 'file', size: 5, modified_at: '2026-09-19T00:00:00Z' };
const listing = (entries: StorageEntry[]): StorageListing => ({ path: '', entries, skipped: 0, max_file_bytes: 64 * 1024 * 1024 });
afterEach(() => { cleanup(); vi.resetAllMocks(); });
beforeEach(() => { vi.mocked(storageApi.list).mockResolvedValue(listing([])); });

it('creates a directory and navigates into it', async () => {
  const folder = { ...file, name: 'docs', path: 'docs', kind: 'directory' as const, size: null };
  render(<StorageView />);
  await screen.findByText(/当前目录为空/);
  fireEvent.click(screen.getByRole('button', { name: '新建文件夹' }));
  fireEvent.change(screen.getByLabelText('文件夹名称'), { target: { value: 'docs' } });
  vi.mocked(storageApi.mkdir).mockResolvedValue(folder);
  vi.mocked(storageApi.list).mockResolvedValue(listing([folder]));
  fireEvent.click(screen.getByRole('button', { name: '保存' }));
  const open = await screen.findByRole('button', { name: 'docs' });
  expect(storageApi.mkdir).toHaveBeenCalledWith('', 'docs');
  vi.mocked(storageApi.list).mockResolvedValue({ ...listing([]), path: 'docs' });
  fireEvent.click(open);
  await waitFor(() => expect(storageApi.list).toHaveBeenCalledWith('docs', expect.any(AbortSignal)));
});

it('uploads the selected bytes and downloads an authenticated blob', async () => {
  const upload = new File(['hello'], 'actual.txt');
  vi.mocked(storageApi.upload).mockResolvedValue(file);
  render(<StorageView />);
  await screen.findByText(/当前目录为空/);
  vi.mocked(storageApi.list).mockResolvedValue(listing([file]));
  fireEvent.change(screen.getByLabelText('选择上传文件'), { target: { files: [upload] } });
  await screen.findByText('已上传 actual.txt');
  expect(storageApi.upload).toHaveBeenCalledWith('', upload, expect.any(AbortSignal));
  const blob = new Blob(['hello']);
  vi.mocked(storageApi.download).mockResolvedValue(blob);
  fireEvent.click(await screen.findByRole('button', { name: '下载 actual.txt' }));
  await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(blob, 'actual.txt'));
});

it('requires confirmation to delete and preserves the file on server failure', async () => {
  vi.mocked(storageApi.list).mockResolvedValue(listing([file]));
  vi.mocked(storageApi.remove).mockRejectedValue(new Error('File is in use'));
  render(<StorageView />);
  fireEvent.click(await screen.findByRole('button', { name: '删除 actual.txt' }));
  expect(storageApi.remove).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
  expect((await screen.findByRole('alert')).textContent).toContain('File is in use');
  expect(screen.getByText('actual.txt')).toBeTruthy();
  expect(screen.queryByText('已删除')).toBeNull();
});

it('clears stale listings when a refresh fails', async () => {
  vi.mocked(storageApi.list).mockResolvedValueOnce(listing([file])).mockRejectedValueOnce(new Error('offline'));
  render(<StorageView />);
  await screen.findByText('actual.txt');
  fireEvent.click(screen.getByRole('button', { name: '刷新' }));
  await screen.findByRole('alert');
  expect(screen.queryByText('actual.txt')).toBeNull();
});
