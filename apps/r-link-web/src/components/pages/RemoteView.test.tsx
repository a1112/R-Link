import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { devicesApi } from '../../api/devices';
import { RemoteView } from './RemoteView';
vi.mock('../../api/devices', () => ({ devicesApi: { list: vi.fn(), save: vi.fn(), probe: vi.fn(), remove: vi.fn(), export: vi.fn(), import: vi.fn() } }));
vi.mock('../../utils/download', () => ({ saveBlob: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const device = { id: 'one', name: 'NAS', host: '192.0.2.1', port: 22, username: 'admin', revision: 1, status: 'unchecked' as const, checked_at: null, latency_ms: null };
it('adds a persisted device, shows measured status, passes SSH target and confirms deletion', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([]);
  vi.mocked(devicesApi.save).mockResolvedValue(device);
  vi.mocked(devicesApi.probe).mockResolvedValue({ ...device, status: 'reachable', checked_at: '2026-09-19T00:00:00Z', latency_ms: 12 });
  vi.mocked(devicesApi.remove).mockResolvedValue(undefined);
  const onSsh = vi.fn();
  render(<RemoteView onSsh={onSsh} />);
  await screen.findByText(/尚未登记设备/);
  fireEvent.click(screen.getByRole('button', { name: '添加设备' }));
  fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'NAS' } });
  fireEvent.change(screen.getByLabelText('主机名或 IP'), { target: { value: '192.0.2.1' } });
  fireEvent.click(screen.getByRole('button', { name: '保存设备' }));
  await screen.findByText('尚未检测');
  expect(devicesApi.save).toHaveBeenCalledWith({ name: 'NAS', host: '192.0.2.1', port: 22, username: '' }, undefined);
  fireEvent.click(screen.getByRole('button', { name: '检测端口' }));
  await screen.findByText(/端口可达 · 12 ms/);
  fireEvent.click(screen.getByRole('button', { name: 'SSH 连接' }));
  expect(onSsh).toHaveBeenCalledWith(expect.objectContaining({ host: '192.0.2.1', port: 22 }));
  fireEvent.click(screen.getByRole('button', { name: '删除' }));
  expect(devicesApi.remove).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
  await waitFor(() => expect(screen.queryByText('NAS')).toBeNull());
});
it('shows API failure instead of fabricating online devices', async () => {
  vi.mocked(devicesApi.list).mockRejectedValue(new Error('offline'));
  render(<RemoteView />);
  expect((await screen.findByRole('alert')).textContent).toContain('offline');
  expect(screen.queryByText('NAS')).toBeNull();
});

it('checks only the filtered devices and shows measured results', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([device, { ...device, id: 'two', name: 'Laptop', host: '192.0.2.2' }]);
  vi.mocked(devicesApi.probe).mockResolvedValue({ ...device, status: 'reachable', latency_ms: 5, checked_at: '2026-09-19T00:00:00Z' });
  render(<RemoteView />);
  await screen.findByText('Laptop');
  fireEvent.change(screen.getByLabelText('搜索设备'), { target: { value: 'NAS' } });
  expect(screen.queryByText('Laptop')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '检测筛选结果 (1)' }));
  await screen.findByText('批量检测结束：完成 1/1');
  expect(devicesApi.probe).toHaveBeenCalledWith('one', expect.any(AbortSignal));
  expect(devicesApi.probe).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText('检测状态筛选'), { target: { value: 'unreachable' } });
  expect(screen.getByText('没有符合筛选条件的设备。')).toBeTruthy();
});

it('previews an import and reports actual added and skipped counts', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([]);
  vi.mocked(devicesApi.import).mockResolvedValue({ added: 1, skipped: 1 });
  const inventory = { version: 1, devices: [{ name: 'NAS', host: 'nas.example' }] };
  const file = new File([''], 'devices.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify(inventory) });
  render(<RemoteView />);
  await screen.findByText(/尚未登记设备/);
  fireEvent.change(screen.getByLabelText('选择设备清单'), { target: { files: [file] } });
  await screen.findByRole('dialog', { name: '导入设备清单' });
  expect(devicesApi.import).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认导入' }));
  expect(await screen.findByText('导入完成：新增 1 台，跳过 1 台。')).toBeTruthy();
  expect(devicesApi.import).toHaveBeenCalledWith(inventory);
});
