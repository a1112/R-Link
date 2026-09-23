import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { servicesApi } from '../../api/services';
import { saveBlob } from '../../utils/download';
vi.mock('../../api/services', () => ({ servicesApi: {
  capabilities: vi.fn(), downloads: vi.fn(), createDownload: vi.fn(), downloadAction: vi.fn(), deleteDownload: vi.fn(), downloadFile: vi.fn(),
  tunnels: vi.fn(), saveTunnel: vi.fn(), tunnelAction: vi.fn(), tunnelLogs: vi.fn(), deleteTunnel: vi.fn(),
  domains: vi.fn(), domainStatus: vi.fn(), saveDomain: vi.fn(), domainAction: vi.fn(), domainLogs: vi.fn(), checkDomain: vi.fn(), dns: vi.fn(),
} }));
vi.mock('../../utils/download', () => ({ saveBlob: vi.fn() }));
import { DownloadsView } from './DownloadsView';
import { FRPView } from './FRPView';
import { DomainView } from './DomainView';

afterEach(() => { cleanup(); vi.resetAllMocks(); });
beforeEach(() => {
  vi.mocked(servicesApi.downloads).mockResolvedValue([]);
  vi.mocked(servicesApi.tunnels).mockResolvedValue([]);
  vi.mocked(servicesApi.domains).mockResolvedValue([]);
  vi.mocked(servicesApi.capabilities).mockResolvedValue({ ready: true, frp: { available: false, reason: '未安装 frpc' }, https: { available: true, reason: null }, downloads: { available: true, max_bytes: 1024 } });
  vi.mocked(servicesApi.domainStatus).mockResolvedValue({ state: 'stopped', pid: null, error: null, pending_changes: true, dns_configured: false });
});

it('creates a real download request and shows server failures', async () => {
  vi.mocked(servicesApi.createDownload).mockRejectedValue(new Error('下载任务已达上限'));
  render(<DownloadsView />);
  await screen.findByText('暂无下载任务。');
  fireEvent.change(screen.getByLabelText('下载地址'), { target: { value: 'https://example.com/file' } });
  fireEvent.change(screen.getByLabelText('保存名称'), { target: { value: 'file.zip' } });
  fireEvent.click(screen.getByRole('button', { name: '添加下载' }));
  expect((await screen.findByRole('alert')).textContent).toContain('下载任务已达上限');
  expect(servicesApi.createDownload).toHaveBeenCalledWith('https://example.com/file', 'file.zip');
});

it('pauses a task and continues from the persisted state', async () => {
  const item = { id: 'one', name: 'archive.zip', url: 'https://example.com/a', state: 'running' as const, downloaded: 100, total: 200, error: null };
  vi.mocked(servicesApi.downloads).mockResolvedValue([item]);
  render(<DownloadsView />);
  const pause = await screen.findByRole('button', { name: '暂停' });
  vi.mocked(servicesApi.downloads).mockResolvedValue([{ ...item, state: 'paused' }]);
  fireEvent.click(pause);
  fireEvent.click(await screen.findByRole('button', { name: '继续' }));
  await waitFor(() => expect(servicesApi.downloadAction).toHaveBeenCalledWith('one', 'resume'));
  expect(servicesApi.downloadAction).toHaveBeenCalledWith('one', 'pause');
});

it('saves the authenticated file and confirms deletion', async () => {
  const item = { id: 'one', name: 'archive.zip', url: 'https://example.com/a', state: 'completed' as const, downloaded: 200, total: 200, error: null };
  vi.mocked(servicesApi.downloads).mockResolvedValue([item]);
  const blob = new Blob(['actual bytes']);
  vi.mocked(servicesApi.downloadFile).mockResolvedValue(blob);
  render(<DownloadsView />);
  fireEvent.click(await screen.findByRole('button', { name: '保存到本机' }));
  await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(blob, 'archive.zip'));
  await waitFor(() => expect((screen.getByRole('button', { name: '删除' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '删除' }));
  expect(servicesApi.deleteDownload).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
  await waitFor(() => expect(servicesApi.deleteDownload).toHaveBeenCalledWith('one'));
});

it('saves a tunnel without inventing a running connection or sending secrets', async () => {
  render(<FRPView />);
  await screen.findByText('未安装 frpc');
  fireEvent.click(screen.getByRole('button', { name: '新建隧道' }));
  fireEvent.change(screen.getByLabelText('隧道名称'), { target: { value: 'home-ssh' } });
  fireEvent.change(screen.getByLabelText('frps 服务器地址'), { target: { value: 'frp.example.com' } });
  fireEvent.click(screen.getByRole('button', { name: '保存' }));
  await waitFor(() => expect(servicesApi.saveTunnel).toHaveBeenCalledWith(expect.objectContaining({ name: 'home-ssh', server_host: 'frp.example.com', token_env: 'R_LINK_FRP_TOKEN' }), undefined));
  expect(screen.queryByText('进程运行中')).toBeNull();
});

it('keeps domain edits separate from applying HTTPS and reports apply failure', async () => {
  vi.mocked(servicesApi.domainAction).mockRejectedValue(new Error('Caddy 端口被占用'));
  render(<DomainView />);
  await screen.findByText(/有尚未应用的配置/);
  fireEvent.click(screen.getByRole('button', { name: '添加域名' }));
  fireEvent.change(screen.getByLabelText('域名'), { target: { value: 'app.example.com' } });
  fireEvent.click(screen.getByRole('button', { name: '保存' }));
  await waitFor(() => expect(servicesApi.saveDomain).toHaveBeenCalledWith(expect.objectContaining({ hostname: 'app.example.com', upstream_port: 8080 }), undefined));
  expect(servicesApi.domainAction).not.toHaveBeenCalled();
  await waitFor(() => expect((screen.getByRole('button', { name: '应用 HTTPS' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '应用 HTTPS' }));
  expect((await screen.findByRole('alert')).textContent).toContain('Caddy 端口被占用');
});
