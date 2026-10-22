import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clashApi } from '../../api/clash';
import { trafficApi, type ClashTrafficSnapshot } from '../../api/traffic';

vi.mock('../../api/clash', () => ({ clashApi: { status: vi.fn(), closeConnection: vi.fn() } }));
vi.mock('../../api/traffic', async () => {
  const actual = await vi.importActual<typeof import('../../api/traffic')>('../../api/traffic');
  return { ...actual, trafficApi: { snapshot: vi.fn() } };
});
vi.mock('../NetworkMonitor', () => ({ NetworkMonitor: () => <div data-testid="network-monitor">网卡监控</div> }));

import { TrafficView } from './TrafficView';

const connectedStatus = {
  configured: true,
  connected: true,
  controller_url: 'http://clash.example:9090',
  version: '1.0.0',
  error: null,
  managed: { available: false, state: 'stopped', pid: null, error: null, profile_id: null },
};

const connection = (id: string, host: string, process: string) => ({
  id,
  start: '2026-10-11T00:00:00Z',
  upload: 10,
  download: 20,
  chains: ['Proxy'],
  rule: 'MATCH',
  metadata: {
    network: 'tcp',
    type: 'HTTP',
    sourceIP: '10.0.0.2',
    sourcePort: 1234,
    destinationIP: '203.0.113.10',
    destinationPort: 443,
    host,
    process,
  },
});

const snapshot = (connections = [connection('c1', 'example.com', 'Browser')], sampledAt = 100): ClashTrafficSnapshot => ({
  sampled_at: sampledAt,
  source_id: 'api-server-a',
  downloadTotal: sampledAt * 10,
  uploadTotal: sampledAt * 5,
  connections,
  total_connections: connections.length,
  truncated: false,
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

beforeEach(() => {
  vi.mocked(clashApi.status).mockResolvedValue(connectedStatus);
  vi.mocked(clashApi.closeConnection).mockResolvedValue(undefined);
  vi.mocked(trafficApi.snapshot).mockResolvedValue(snapshot());
});

it('gates traffic sampling on Clash status and offers configuration navigation', async () => {
  vi.mocked(clashApi.status).mockResolvedValue({ ...connectedStatus, configured: false, connected: false });
  const onConfigureClash = vi.fn();
  render(<TrafficView onConfigureClash={onConfigureClash} />);
  expect(await screen.findByText(/Clash 尚未配置/)).toBeTruthy();
  expect(trafficApi.snapshot).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '前往 Clash 配置' }));
  expect(onConfigureClash).toHaveBeenCalledTimes(1);
});

it('shows an explicit confirmation before disconnecting one connection', async () => {
  render(<TrafficView />);
  expect(await screen.findByRole('button', { name: '断开连接' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '断开连接' }));
  expect(screen.getByRole('dialog', { name: '确认断开 Clash 连接' })).toBeTruthy();
  expect(clashApi.closeConnection).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认断开' }));
  await waitFor(() => expect(clashApi.closeConnection).toHaveBeenCalledWith('c1', 'api-server-a'));
});

it('cancels a pending confirmation when the traffic source changes', async () => {
  vi.mocked(trafficApi.snapshot)
    .mockResolvedValueOnce(snapshot())
    .mockResolvedValueOnce({ ...snapshot([], 101), source_id: 'api-server-b' });
  render(<TrafficView />);
  await screen.findByRole('button', { name: '断开连接' });
  fireEvent.click(screen.getByRole('button', { name: '断开连接' }));
  expect(screen.getByRole('dialog', { name: '确认断开 Clash 连接' })).toBeTruthy();

  fireEvent.click(screen.getByRole('button', { name: '手动刷新' }));
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '确认断开 Clash 连接' })).toBeNull());
  expect(clashApi.closeConnection).not.toHaveBeenCalled();
  expect(screen.queryByRole('alert')).toBeNull();
});

it('ignores a late snapshot from an old controller target', async () => {
  let resolveOld!: (value: ClashTrafficSnapshot) => void;
  let resolveNew!: (value: ClashTrafficSnapshot) => void;
  const oldRequest = new Promise<ClashTrafficSnapshot>(resolve => { resolveOld = resolve; });
  const newRequest = new Promise<ClashTrafficSnapshot>(resolve => { resolveNew = resolve; });
  vi.mocked(clashApi.status)
    .mockResolvedValueOnce(connectedStatus)
    .mockResolvedValue({ ...connectedStatus, controller_url: 'http://clash-new.example:9090' });
  vi.mocked(trafficApi.snapshot)
    .mockReturnValueOnce(oldRequest)
    .mockReturnValueOnce(newRequest);

  render(<TrafficView />);
  await waitFor(() => expect(trafficApi.snapshot).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: '手动刷新' }));
  await waitFor(() => expect(trafficApi.snapshot).toHaveBeenCalledTimes(2));

  resolveOld(snapshot([connection('old', 'old.example', 'Old')], 101));
  await waitFor(() => expect(screen.queryByRole('checkbox', { name: '选择 old.example:443' })).toBeNull());
  resolveNew(snapshot([connection('new', 'new.example', 'New')], 101));
  expect(await screen.findByRole('checkbox', { name: '选择 new.example:443' })).toBeTruthy();
});

it('clears loading when paused and still allows a manual refresh', async () => {
  let resolveInitial!: (value: ClashTrafficSnapshot) => void;
  const initialRequest = new Promise<ClashTrafficSnapshot>(resolve => { resolveInitial = resolve; });
  vi.mocked(trafficApi.snapshot)
    .mockReturnValueOnce(initialRequest)
    .mockResolvedValueOnce(snapshot([connection('manual', 'manual.example', 'Manual')], 101));

  render(<TrafficView />);
  await waitFor(() => expect(trafficApi.snapshot).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: '暂停 Clash 采样' }));
  await waitFor(() => expect(screen.queryByText('正在读取 Clash 流量…')).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: '手动刷新' }));
  expect(await screen.findByRole('checkbox', { name: '选择 manual.example:443' })).toBeTruthy();

  resolveInitial(snapshot([connection('late', 'late.example', 'Late')], 101));
  await waitFor(() => expect(screen.queryByRole('checkbox', { name: '选择 late.example:443' })).toBeNull());
});

it('reports individual failures when selected disconnects partially fail', async () => {
  const second = connection('c2', 'second.example', 'Terminal');
  vi.mocked(trafficApi.snapshot).mockResolvedValue(snapshot([connection('c1', 'example.com', 'Browser'), second]));
  vi.mocked(clashApi.closeConnection).mockImplementation(async id => {
    if (id === 'c2') throw new Error('控制器拒绝');
    return undefined;
  });
  render(<TrafficView />);
  await screen.findByRole('checkbox', { name: '选择 second.example:443' });
  fireEvent.click(screen.getByRole('checkbox', { name: '选择 example.com:443' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '选择 second.example:443' }));
  fireEvent.click(screen.getByRole('button', { name: /断开选中/ }));
  expect(screen.getByRole('dialog', { name: '确认断开 Clash 连接' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '确认断开' }));
  expect((await screen.findByRole('alert')).textContent).toContain('second.example:443 · 10.0.0.2:1234：控制器拒绝');
  expect(clashApi.closeConnection).toHaveBeenCalledWith('c1', 'api-server-a');
  expect(clashApi.closeConnection).toHaveBeenCalledWith('c2', 'api-server-a');
});

it('filters the current connection list by process and protocol', async () => {
  const second = { ...connection('c2', 'second.example', 'Terminal'), metadata: { ...connection('c2', 'second.example', 'Terminal').metadata, network: 'udp', type: 'HTTP' } };
  vi.mocked(trafficApi.snapshot).mockResolvedValue(snapshot([connection('c1', 'example.com', 'Browser'), second]));
  render(<TrafficView />);
  await screen.findByRole('checkbox', { name: '选择 second.example:443' });
  fireEvent.change(screen.getByLabelText('搜索目标、来源或进程'), { target: { value: 'Terminal' } });
  const table = screen.getByRole('table');
  expect(table.textContent).toContain('second.example');
  expect(table.textContent).not.toContain('example.com');
  fireEvent.change(screen.getByLabelText('协议筛选'), { target: { value: 'tcp' } });
  expect(screen.queryByRole('table')).toBeNull();
});
