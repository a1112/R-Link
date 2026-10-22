import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { clashApi } from '../../api/clash';
import { trafficApi } from '../../api/traffic';
import { ClashView } from './ClashView';

vi.mock('../../api/traffic', () => ({ trafficApi: { snapshot: vi.fn() } }));

vi.mock('../../api/clash', () => ({
  clashApi: {
    settings: vi.fn(),
    saveSettings: vi.fn(),
    status: vi.fn(),
    configs: vi.fn(),
    updateConfigs: vi.fn(),
    proxies: vi.fn(),
    selectProxy: vi.fn(),
    proxyDelay: vi.fn(),
    rules: vi.fn(),
    connections: vi.fn(),
    closeConnection: vi.fn(),
    closeAllConnections: vi.fn(),
    providers: vi.fn(),
    refreshProvider: vi.fn(),
    profiles: vi.fn(),
    createProfile: vi.fn(),
    deleteProfile: vi.fn(),
    startManaged: vi.fn(),
    stopManaged: vi.fn(),
  },
}));

afterEach(() => { cleanup(); vi.resetAllMocks(); if (typeof localStorage !== 'undefined') localStorage.clear(); if (typeof sessionStorage !== 'undefined') sessionStorage.clear(); });

beforeEach(() => {
  vi.mocked(clashApi.settings).mockResolvedValue({ controller_url: '', has_secret: false });
  vi.mocked(clashApi.status).mockResolvedValue({ configured: false, connected: false, controller_url: '', version: null, error: null, managed: { available: false, state: 'stopped', pid: null, error: null, profile_id: null } });
  vi.mocked(clashApi.saveSettings).mockResolvedValue({ controller_url: 'http://clash.example:9090', has_secret: true });
  vi.mocked(clashApi.profiles).mockResolvedValue([]);
  vi.mocked(trafficApi.snapshot).mockResolvedValue({ sampled_at: 1, source_id: 'snapshot-source-a', uploadTotal: 0, downloadTotal: 0, total_connections: 1, truncated: false, connections: [{ id: 'c1', start: '', upload: 0, download: 0, chains: [], rule: '', metadata: null }] });
});

it('binds both legacy connection close operations to the sampled source', async () => {
  vi.mocked(clashApi.status).mockResolvedValue({ configured: true, connected: true, controller_url: 'http://127.0.0.1:9090', version: '1', error: null, managed: { available: true, state: 'stopped', pid: null, error: null, profile_id: null } });
  render(<ClashView />);
  await screen.findByText('已连接');
  fireEvent.click(screen.getByRole('tab', { name: '连接' }));
  fireEvent.click(await screen.findByRole('button', { name: '关闭连接' }));
  await waitFor(() => expect(clashApi.closeConnection).toHaveBeenCalledWith('c1', 'snapshot-source-a'));
  await waitFor(() => expect((screen.getByRole('button', { name: '关闭全部连接' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '关闭全部连接' }));
  fireEvent.click(screen.getByRole('button', { name: '确认关闭全部' }));
  await waitFor(() => expect(clashApi.closeAllConnections).toHaveBeenCalledWith('snapshot-source-a'));
});

it('cancels a legacy close-all confirmation when its snapshot source changes', async () => {
  vi.mocked(clashApi.status).mockResolvedValue({ configured: true, connected: true, controller_url: 'http://127.0.0.1:9090', version: '1', error: null, managed: { available: true, state: 'stopped', pid: null, error: null, profile_id: null } });
  render(<ClashView />);
  await screen.findByText('已连接');
  fireEvent.click(screen.getByRole('tab', { name: '连接' }));
  fireEvent.click(await screen.findByRole('button', { name: '关闭全部连接' }));
  vi.mocked(trafficApi.snapshot).mockResolvedValue({ sampled_at: 2, source_id: 'snapshot-source-b', uploadTotal: 0, downloadTotal: 0, connections: [], total_connections: 0, truncated: false });
  fireEvent.click(screen.getByRole('button', { name: '刷新连接' }));
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '关闭全部 Clash 连接' })).toBeNull());
  expect(clashApi.closeAllConnections).not.toHaveBeenCalled();
});

it('keeps a blank password out of the settings payload and does not persist it in browser storage', async () => {
  render(<ClashView />);
  await screen.findByText('未配置');
  fireEvent.change(screen.getByLabelText('控制器 URL'), { target: { value: 'http://clash.example:9090' } });
  fireEvent.click(screen.getByRole('button', { name: '保存并连接' }));
  await waitFor(() => expect(clashApi.saveSettings).toHaveBeenCalledWith({ controller_url: 'http://clash.example:9090' }));
  if (typeof localStorage !== 'undefined') expect(localStorage.length).toBe(0);
  if (typeof sessionStorage !== 'undefined') expect(sessionStorage.length).toBe(0);
});

it('does not request noisy Clash panels while the controller is disconnected', async () => {
  render(<ClashView />);
  await screen.findByText('未配置');
  fireEvent.click(screen.getByRole('tab', { name: '代理组' }));
  expect(clashApi.proxies).not.toHaveBeenCalled();
  expect(clashApi.rules).not.toHaveBeenCalled();
  expect(clashApi.connections).not.toHaveBeenCalled();
});

it('loads a selected panel only after the real status reports connected', async () => {
  vi.mocked(clashApi.status).mockResolvedValue({ configured: true, connected: true, controller_url: 'http://clash.example:9090', version: '1.0.0', error: null, managed: { available: true, state: 'stopped', pid: null, error: null, profile_id: null } });
  vi.mocked(clashApi.proxies).mockResolvedValue({ proxies: { Auto: { name: 'Auto', type: 'Selector', now: 'Tokyo', all: ['Tokyo'], alive: true } } });
  render(<ClashView />);
  await screen.findByText('已连接');
  fireEvent.click(screen.getByRole('tab', { name: '代理组' }));
  expect(await screen.findByText('Auto')).toBeTruthy();
  expect(clashApi.proxies).toHaveBeenCalled();
});

it('only renders a manual switch for Selector groups', async () => {
  vi.mocked(clashApi.status).mockResolvedValue({ configured: true, connected: true, controller_url: 'http://clash.example:9090', version: '1.0.0', error: null, managed: { available: true, state: 'stopped', pid: null, error: null, profile_id: null } });
  vi.mocked(clashApi.proxies).mockResolvedValue({ proxies: {
    Manual: { name: 'Manual', type: 'Selector', now: 'Tokyo', all: ['Tokyo', 'Osaka'], alive: true },
    Balanced: { name: 'Balanced', type: 'LoadBalance', now: 'Tokyo', all: ['Tokyo', 'Osaka'], alive: true },
  } });
  render(<ClashView />);
  await screen.findByText('已连接');
  fireEvent.click(screen.getByRole('tab', { name: '代理组' }));
  await screen.findByText('Balanced');
  expect(screen.getByLabelText('Manual 节点')).toBeTruthy();
  expect(screen.queryByLabelText('Balanced 节点')).toBeNull();
  expect(screen.getByText('自动选择组')).toBeTruthy();
});

it('keeps the server-selected node visible when a selection request fails', async () => {
  vi.mocked(clashApi.status).mockResolvedValue({ configured: true, connected: true, controller_url: 'http://clash.example:9090', version: '1.0.0', error: null, managed: { available: true, state: 'stopped', pid: null, error: null, profile_id: null } });
  vi.mocked(clashApi.proxies).mockResolvedValue({ proxies: { Manual: { name: 'Manual', type: 'Selector', now: 'Tokyo', all: ['Tokyo', 'Osaka'], alive: true } } });
  vi.mocked(clashApi.selectProxy).mockRejectedValue(new Error('控制器拒绝切换'));
  render(<ClashView />);
  await screen.findByText('已连接');
  fireEvent.click(screen.getByRole('tab', { name: '代理组' }));
  const selector = await screen.findByLabelText('Manual 节点') as HTMLSelectElement;
  fireEvent.change(selector, { target: { value: 'Osaka' } });
  await screen.findByRole('alert');
  expect(selector.value).toBe('Tokyo');
});

it('remounts a selected panel when the connected API target changes', async () => {
  const external = { configured: true, connected: true, controller_url: 'http://external.example:9090', version: '1.0.0', error: null, managed: { available: true, state: 'stopped' as const, pid: null, error: null, profile_id: null } };
  const managed = { configured: true, connected: true, controller_url: 'http://127.0.0.1:34567', version: '1.0.0', error: null, managed: { available: true, state: 'running' as const, pid: 42, error: null, profile_id: 'profile-1' } };
  vi.mocked(clashApi.status).mockResolvedValue(external);
  vi.mocked(clashApi.proxies)
    .mockResolvedValueOnce({ proxies: { External: { name: 'External', type: 'Selector', now: 'Tokyo', all: ['Tokyo'], alive: true } } })
    .mockResolvedValue({ proxies: { Managed: { name: 'Managed', type: 'Selector', now: 'Osaka', all: ['Osaka'], alive: true } } });
  render(<ClashView />);
  await screen.findByText('已连接');
  fireEvent.click(screen.getByRole('tab', { name: '代理组' }));
  await screen.findByText('External');
  vi.mocked(clashApi.status).mockResolvedValue(managed);
  fireEvent.click(screen.getByRole('button', { name: '刷新状态' }));
  await screen.findByText('Managed');
  expect(screen.queryByText('External')).toBeNull();
  expect(clashApi.proxies).toHaveBeenCalledTimes(2);
});

it('shows a stop error from the managed core action', async () => {
  vi.mocked(clashApi.status).mockResolvedValue({ configured: true, connected: true, controller_url: 'http://127.0.0.1:34567', version: '1.0.0', error: null, managed: { available: true, state: 'running', pid: 42, error: null, profile_id: 'profile-1' } });
  vi.mocked(clashApi.stopManaged).mockRejectedValue(new Error('Mihomo 停止失败'));
  render(<ClashView />);
  await screen.findByText('已连接');
  fireEvent.click(screen.getByRole('button', { name: '停止受管内核' }));
  expect((await screen.findByRole('alert')).textContent).toContain('Mihomo 停止失败');
});
