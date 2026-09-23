import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { devicesApi } from '../api/devices';
vi.mock('../api/devices', () => ({ devicesApi: { list: vi.fn() } }));
vi.mock('../api/hooks', () => ({ useSystemInfo: () => ({ data: { hostname: 'real-server' } }) }));
import { TopologyView } from './TopologyView';
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it('renders registered devices and passes the actual SSH target', async () => {
  const device = { id: '1', name: 'Registered NAS', host: '::1', port: 22, username: 'owner', revision: 1, status: 'reachable' as const, checked_at: '2026-09-19T00:00:00Z', latency_ms: 3 };
  vi.mocked(devicesApi.list).mockResolvedValue([device]);
  const onSsh = vi.fn();
  render(<TopologyView onSsh={onSsh} />);
  expect(await screen.findByText('Registered NAS')).toBeTruthy();
  expect(screen.getByText('[::1]:22')).toBeTruthy();
  expect(screen.getByText('上次检测：端口可达')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'SSH 连接' }));
  expect(onSsh).toHaveBeenCalledWith(device);
});
it('shows no invented devices when the backend has none or fails', async () => {
  vi.mocked(devicesApi.list).mockResolvedValueOnce([]).mockRejectedValueOnce(new Error('offline'));
  render(<TopologyView />);
  expect(await screen.findByText('尚未登记设备')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '刷新状态' }));
  expect((await screen.findByRole('alert')).textContent).toContain('offline');
  expect(screen.queryByText('尚未登记设备')).toBeNull();
});
