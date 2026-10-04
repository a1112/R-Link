import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { devicesApi, type Device } from '../../api/devices';
import { rfileApi, type RFileStatus } from '../../api/rfile';
vi.mock('../../api/devices', () => ({ devicesApi: { list: vi.fn() } }));
vi.mock('../../api/rfile', () => ({ rfileApi: { status: vi.fn() } }));
vi.mock('../../api/system', () => ({ systemApi: { getInfo: vi.fn(async () => ({ hostname: 'real-server', system: 'Linux' })) } }));
import { TopologyView } from '../TopologyView';
const nas: Device = { id: 'nas', name: 'Registered NAS', host: '::1', port: 22, username: 'owner', revision: 1, status: 'reachable', checked_at: '2026-10-04T00:00:00Z', latency_ms: 3, device_type: 'nas', platform: 'linux', connection_status: 'online' };
const bridge: RFileStatus = { watch: { url: '', state: 'offline', error: null, checked_at: null }, network: { url: '', state: 'online', controller_registered: true, active_sessions: 0, error: null, checked_at: null }, files: { enabled: false, max_file_bytes: 0, reason: null }, devices: [], config_error: null };
beforeEach(() => { vi.mocked(devicesApi.list).mockResolvedValue([nas]); vi.mocked(rfileApi.status).mockResolvedValue(bridge); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const select = async (name = 'Registered NAS') => fireEvent.click(await screen.findByRole('button', { name: `查看设备：${name}` }));

it('selects real details, passes the SSH target and restores focus when closed', async () => {
  const onSsh = vi.fn(); render(<TopologyView onSsh={onSsh} />);
  expect(screen.queryByRole('complementary')).toBeNull(); await select();
  const detail = screen.getByRole('complementary', { name: '设备详情' });
  expect(within(detail).getByText('[::1]:22')).toBeTruthy();
  expect(within(detail).getByText('端口可达 · 3 ms')).toBeTruthy();
  fireEvent.click(within(detail).getByRole('button', { name: 'SSH 连接' }));
  expect(onSsh).toHaveBeenCalledWith(nas);
  fireEvent.keyDown(detail, { key: 'Escape' });
  expect(screen.queryByRole('complementary')).toBeNull();
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '查看设备：Registered NAS' }));
});
it('counts and filters presence independently of TCP and gateway state', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([nas, { ...nas, id: 'off', name: 'Offline PC', connection_status: 'offline' }, { ...nas, id: 'unk', name: 'Unknown phone', device_type: 'mobile', connection_status: 'unknown', gateway_status: 'online' }]);
  render(<TopologyView />); await select();
  expect(screen.getByRole('button', { name: '在线设备 1' })).toBeTruthy();
  expect(screen.getByRole('button', { name: '未知设备 1' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '离线设备 1' }));
  expect(screen.queryByRole('button', { name: '查看设备：Registered NAS' })).toBeNull();
  expect(screen.getByRole('button', { name: '查看设备：Offline PC' })).toBeTruthy();
  expect(screen.queryByRole('complementary')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '全部设备 3' }));
  fireEvent.change(screen.getByLabelText('搜索设备'), { target: { value: 'phone' } });
  expect(screen.queryByRole('button', { name: '查看设备：Offline PC' })).toBeNull();
  expect(screen.getByRole('button', { name: '查看设备：Unknown phone' })).toBeTruthy();
});
it('combines source/type filters and offers no sample devices for empty inventory', async () => {
  vi.mocked(rfileApi.status).mockResolvedValue({ ...bridge, devices: [{ deviceId: 'p', deviceName: 'Peer phone', platform: 'android', presence: 'online' }] });
  render(<TopologyView />); await select('Peer phone');
  fireEvent.change(screen.getByLabelText('设备来源'), { target: { value: 'rfile' } });
  fireEvent.change(screen.getByLabelText('设备类型'), { target: { value: 'nas' } });
  expect(screen.getByText('没有符合筛选条件的设备')).toBeTruthy();
  cleanup(); vi.mocked(devicesApi.list).mockResolvedValue([]); vi.mocked(rfileApi.status).mockResolvedValue(bridge);
  render(<TopologyView />); expect(await screen.findByText('尚未发现设备')).toBeTruthy();
  expect(screen.queryByText('家庭 NAS')).toBeNull();
});
it('clears stale failed inventory but retains independently loaded R-File peers', async () => {
  vi.mocked(devicesApi.list).mockResolvedValueOnce([nas]).mockRejectedValue(new Error('inventory offline'));
  vi.mocked(rfileApi.status).mockResolvedValue({ ...bridge, devices: [{ deviceId: 'peer', deviceName: 'Actual peer', presence: 'online' }] });
  render(<TopologyView />); await select(); fireEvent.click(screen.getByRole('button', { name: '刷新状态' }));
  expect((await screen.findByRole('alert')).textContent).toContain('inventory offline');
  expect(screen.queryByRole('button', { name: '查看设备：Registered NAS' })).toBeNull();
  expect(screen.queryByRole('complementary')).toBeNull();
  expect(screen.getByRole('button', { name: '查看设备：Actual peer' })).toBeTruthy();
});
it('keeps loaded devices usable while another source is still loading', async () => {
  vi.mocked(rfileApi.status).mockReturnValue(new Promise(() => {}));
  render(<TopologyView />); await select();
  expect(screen.getByRole('complementary', { name: '设备详情' })).toBeTruthy();
  expect(screen.queryByText('正在读取设备…')).toBeNull();
  expect(screen.getByText('正在读取R-File…').getAttribute('role')).toBe('status');
});
it('updates selected details from new snapshots and closes them when removed', async () => {
  vi.mocked(devicesApi.list).mockResolvedValueOnce([nas]).mockResolvedValueOnce([{ ...nas, host: '192.0.2.99', connection_status: 'offline' }]).mockResolvedValue([]);
  render(<TopologyView />); await select(); fireEvent.click(screen.getByRole('button', { name: '刷新状态' }));
  await screen.findByText('192.0.2.99:22'); fireEvent.click(screen.getByRole('button', { name: '刷新状态' }));
  await waitFor(() => expect(screen.queryByRole('complementary')).toBeNull());
});
it('shows gateway state separately and offers only supported safe access', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([{ ...nas, source: 'gateway', connection_status: 'unknown', gateway_status: 'online', access_mode: 'none' }, { ...nas, id: 'web', name: 'Web NAS', port: 443, access_mode: 'web', web_scheme: 'https' }, { ...nas, id: 'rev', name: 'Revoked PC', connection_status: 'revoked' }]);
  render(<TopologyView onSsh={vi.fn()} />); await select();
  expect(within(screen.getByRole('complementary')).getByText('网关状态')).toBeTruthy();
  expect(within(screen.getByRole('complementary')).getByText('未知')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'SSH 连接' })).toBeNull();
  await select('Web NAS'); expect(screen.getByRole('link', { name: '打开 Web 服务' }).getAttribute('href')).toBe('https://[::1]:443/');
  await select('Revoked PC'); expect(screen.queryByRole('button', { name: 'SSH 连接' })).toBeNull();
});
it('routes R-File peers to the service without inventing SSH or per-peer file access', async () => {
  vi.mocked(rfileApi.status).mockResolvedValue({ ...bridge, devices: [{ deviceId: 'p', deviceName: 'RFile peer', presence: 'online', initiationBlockedReason: 'Does not accept remote access' }] });
  const onRFile = vi.fn(); render(<TopologyView onRFile={onRFile} onSsh={vi.fn()} />); await select('RFile peer');
  expect(screen.queryByRole('button', { name: 'SSH 连接' })).toBeNull();
  expect(screen.queryByRole('button', { name: '打开文件' })).toBeNull();
  expect(screen.getByText('Does not accept remote access')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '查看 R-File 服务' })); expect(onRFile).toHaveBeenCalledOnce();
});
it('hands off add/edit actions and bounds/reset zoom', async () => {
  const onManage = vi.fn(); render(<TopologyView onManage={onManage} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '编辑设备' })); expect(onManage).toHaveBeenCalledWith(nas);
  fireEvent.click(screen.getByRole('button', { name: '添加设备' })); expect(onManage).toHaveBeenLastCalledWith();
  for (let i = 0; i < 30; i++) fireEvent.click(screen.getByRole('button', { name: '放大' }));
  expect((screen.getByRole('button', { name: '放大' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText('150%')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '适应视图' })); expect(screen.queryByText('150%')).toBeNull();
});
