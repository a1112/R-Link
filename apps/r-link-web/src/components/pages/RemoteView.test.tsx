import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { act, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { devicesApi } from '../../api/devices';
import { RemoteView } from './RemoteView';
vi.mock('../../api/devices', () => ({ devicesApi: { list: vi.fn(), save: vi.fn(), probe: vi.fn(), remove: vi.fn(), export: vi.fn(), import: vi.fn(), managementStatus: vi.fn(), sync: vi.fn(), onboarding: vi.fn(), link: vi.fn(), revoke: vi.fn() } }));
vi.mock('../../utils/download', () => ({ saveBlob: vi.fn() }));
beforeEach(() => { vi.mocked(devicesApi.managementStatus).mockResolvedValue({ configured: true, syncing: false, interval_seconds: 60, stale_seconds: 180, last_synced_at: null, last_error: null }); });
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.useRealTimers(); });
const device = { id: 'one', name: 'NAS', host: '192.0.2.1', port: 22, username: 'admin', revision: 1, status: 'unchecked' as const, checked_at: null, latency_ms: null };
it('protects Fabric managed addresses and never offers them as LAN gateways or NetBird links', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([{ ...device, source: 'fabric', name: 'Fabric Mac', host: '10.66.0.2', peer_id: 'fabric-peer' }]);
  render(<RemoteView />); await screen.findByText('Fabric Mac');
  expect(screen.queryByRole('button', { name: '关联组网节点' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '编辑' }));
  expect((screen.getByLabelText('主机名或 IP') as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText('接入网关') as HTMLSelectElement).disabled).toBe(true);
});
it('keeps daily device operations but hides NetBird membership management from operators', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([device, { ...device, id: 'peer-device', name: 'Mesh Peer', source: 'netbird', peer_id: 'peer-1', connection_status: 'online' }]);
  render(<RemoteView canManageMembership={false} />);
  await screen.findByText('Mesh Peer');
  expect(screen.getAllByRole('button', { name: '检测端口' })).toHaveLength(2);
  expect(screen.queryByRole('button', { name: '关联组网节点' })).toBeNull();
  expect(screen.queryByRole('button', { name: '撤销入网' })).toBeNull();
});
it('opens the exact topology edit target once after the inventory loads', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([device]);
  const handled = vi.fn();
  render(<RemoteView initialAction={{ kind: 'edit', deviceId: 'one' }} onInitialActionHandled={handled} />);
  expect((await screen.findByLabelText('设备名称') as HTMLInputElement).value).toBe('NAS');
  expect(handled).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  fireEvent.click(screen.getByRole('button', { name: '刷新列表' }));
  await waitFor(() => expect(devicesApi.list).toHaveBeenCalledTimes(2));
  expect(screen.queryByLabelText('设备名称')).toBeNull();
});
it('opens the add form from topology without selecting a different device', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([device]);
  render(<RemoteView initialAction={{ kind: 'add' }} />);
  expect((await screen.findByLabelText('设备名称') as HTMLInputElement).value).toBe('');
});
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
  expect(devicesApi.save).toHaveBeenCalledWith(expect.objectContaining({ name: 'NAS', host: '192.0.2.1', port: 22, username: '' }), undefined, expect.any(AbortSignal));
  fireEvent.click(screen.getByRole('button', { name: '检测端口' }));
  await screen.findByText(/端口可达 · 12 ms/);
  fireEvent.click(screen.getByRole('button', { name: 'SSH 连接' }));
  expect(onSsh).toHaveBeenCalledWith(expect.objectContaining({ host: '192.0.2.1', port: 22 }));
  fireEvent.click(screen.getByRole('button', { name: '删除' }));
  expect(devicesApi.remove).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'NAS' })).toBeNull());
});
it('shows API failure instead of fabricating online devices', async () => {
  vi.mocked(devicesApi.list).mockRejectedValue(new Error('offline'));
  render(<RemoteView />);
  expect((await screen.findByRole('alert')).textContent).toContain('offline');
  expect(screen.queryByRole('heading', { name: 'NAS' })).toBeNull();
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
  expect(devicesApi.import).toHaveBeenCalledWith(inventory, expect.any(AbortSignal));
});

it('edits portable metadata and filters by type, platform, tags and mesh group', async () => {
  const detailed = { ...device, device_type: 'nas' as const, platform: 'linux' as const, tags: ['home'], notes: 'Media', access_mode: 'web' as const, web_scheme: 'https' as const, source: 'manual' as const, mesh_groups: [{ id: 'g', name: 'Family' }] };
  vi.mocked(devicesApi.list).mockResolvedValue([detailed, { ...device, id: 'phone', name: 'Phone', device_type: 'mobile', platform: 'android', access_mode: 'none' }]);
  vi.mocked(devicesApi.save).mockResolvedValue({ ...detailed, tags: ['home', 'backup'], notes: 'Media and backup' });
  render(<RemoteView />);
  await screen.findByText('Phone');
  fireEvent.change(screen.getByLabelText('设备类型筛选'), { target: { value: 'nas' } });
  expect(screen.queryByText('Phone')).toBeNull();
  fireEvent.change(screen.getByLabelText('平台筛选'), { target: { value: 'linux' } });
  fireEvent.change(screen.getByLabelText('标签筛选'), { target: { value: 'home' } });
  fireEvent.change(screen.getByLabelText('搜索设备'), { target: { value: 'Family' } });
  expect(screen.getByRole('heading', { name: 'NAS' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '编辑' }));
  fireEvent.change(screen.getByLabelText('标签（逗号分隔）'), { target: { value: 'home, backup, home' } });
  fireEvent.change(screen.getByLabelText('备注'), { target: { value: 'Media and backup' } });
  fireEvent.click(screen.getByRole('button', { name: '保存设备' }));
  await waitFor(() => expect(devicesApi.save).toHaveBeenCalledWith(expect.objectContaining({ device_type: 'nas', platform: 'linux', tags: ['home', 'backup'], notes: 'Media and backup', access_mode: 'web' }), 'one', expect.any(AbortSignal)));
});

it('does not turn gateway availability or old TCP results into child online status and gates access modes', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([
    { ...device, source: 'gateway', gateway_id: 'router', connection_status: 'unknown', gateway_status: 'online', access_mode: 'none', status: 'reachable', checked_at: '2026-09-19T00:00:00Z' },
    { ...device, id: 'web', name: 'Web NAS', host: '2001:db8::1', port: 443, access_mode: 'web', web_scheme: 'https' },
    { ...device, id: 'gone', name: 'Gone', source: 'netbird', peer_id: 'p', connection_status: 'revoked', access_mode: 'ssh' },
  ]);
  render(<RemoteView onSsh={vi.fn()} />);
  await screen.findByText('Web NAS');
  const child = screen.getByRole('heading', { name: 'NAS' }).closest('article')!;
  expect(within(child).getByText('组网状态：未知')).toBeTruthy();
  expect(within(child).getByText('网关状态：在线')).toBeTruthy();
  expect(within(child).queryByRole('button', { name: 'SSH 连接' })).toBeNull();
  expect(screen.getByRole('link', { name: '打开 Web 服务' }).getAttribute('href')).toBe('https://[2001:db8::1]:443/');
  expect(screen.queryByRole('button', { name: 'SSH 连接' })).toBeNull();
});

it('shows actual sync counts and conflicts and clears old availability on sync failure', async () => {
  const peer = { ...device, source: 'netbird' as const, peer_id: 'p', connection_status: 'online' as const, access_mode: 'none' as const };
  vi.mocked(devicesApi.list).mockResolvedValue([peer]);
  vi.mocked(devicesApi.sync).mockResolvedValueOnce({ added: 2, updated: 1, missing: 3, conflicts: [{ peer_id: 'other-peer', device_id: 'one', host: '192.0.2.1', port: 22, reason: 'endpoint_already_registered' }], synced_at: '2026-10-03T00:00:00Z' }).mockRejectedValueOnce(new Error('upstream unavailable'));
  render(<RemoteView />);
  await screen.findByText('组网状态：在线');
  fireEvent.click(screen.getByRole('button', { name: '同步组网设备' }));
  expect(await screen.findByText('同步完成：新增 2 台，更新 1 台，缺失 3 台，冲突 1 项。')).toBeTruthy();
  expect(screen.getByText(/other-peer.*192\.0\.2\.1:22/)).toBeTruthy();
  vi.mocked(devicesApi.list).mockResolvedValue([{ ...peer, connection_status: 'unknown' }]);
  await waitFor(() => expect((screen.getByRole('button', { name: '同步组网设备' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '同步组网设备' }));
  expect((await screen.findByRole('alert')).textContent).toContain('upstream unavailable');
  expect(screen.queryByText('组网状态：在线')).toBeNull();
});

it('loads onboarding only on request and displays server configuration guidance', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([]);
  vi.mocked(devicesApi.managementStatus).mockResolvedValue({ configured: false, syncing: false, interval_seconds: 60, stale_seconds: 180, last_synced_at: null, last_error: null });
  vi.mocked(devicesApi.onboarding).mockResolvedValue({ configured: false, management_url: null, platforms: [{ id: 'android', name: 'Android', url: 'https://docs.netbird.io/get-started/install/android' }], instructions: ['先配置服务端管理连接'] });
  render(<RemoteView />);
  await screen.findByText(/尚未登记设备/);
  expect(devicesApi.onboarding).not.toHaveBeenCalled();
  expect(screen.getByText(/服务端尚未配置 NetBird/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '设备接入指引' }));
  expect(await screen.findByText('先配置服务端管理连接')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Android' }).getAttribute('href')).toMatch(/^https:\/\/docs.netbird.io/);
});

it('requires explicit peer linking, reports conflicts and retains a failed revoke without success', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([device]);
  vi.mocked(devicesApi.link).mockRejectedValueOnce(new Error('该 peer 已关联另一设备')).mockResolvedValueOnce({ ...device, source: 'netbird', peer_id: 'peer-1', connection_status: 'online' });
  vi.mocked(devicesApi.revoke).mockRejectedValue(new Error('cannot revoke'));
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'NAS' });
  fireEvent.click(screen.getByRole('button', { name: '关联组网节点' }));
  fireEvent.change(screen.getByLabelText('组网 peer ID'), { target: { value: 'peer-1' } });
  expect(devicesApi.link).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认关联' }));
  expect((await screen.findByRole('alert')).textContent).toContain('该 peer 已关联');
  fireEvent.click(screen.getByRole('button', { name: '确认关联' }));
  await screen.findByRole('button', { name: '撤销入网' });
  fireEvent.click(screen.getByRole('button', { name: '撤销入网' }));
  expect(devicesApi.revoke).not.toHaveBeenCalled();
  expect(screen.getByText(/真实组网身份/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '确认撤销入网' }));
  expect((await screen.findByRole('alert')).textContent).toContain('cannot revoke');
  expect(screen.getByText('组网状态：在线')).toBeTruthy();
  expect(screen.queryByText(/已撤销入网/)).toBeNull();
});

it('exports metadata version 2 and distinguishes inventory removal from network revoke', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([device]);
  vi.mocked(devicesApi.export).mockResolvedValue({ version: 2, devices: [device] });
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'NAS' });
  fireEvent.click(screen.getByRole('button', { name: '导出清单' }));
  await waitFor(() => expect(devicesApi.export).toHaveBeenCalledWith(2, expect.any(AbortSignal)));
  await waitFor(() => expect((screen.getByRole('button', { name: '删除' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '删除' }));
  expect(screen.getByText(/删除清单记录不会撤销入网/)).toBeTruthy();
});

it('polls again within five seconds, hides failed snapshots and aborts requests on unmount', async () => {
  vi.useFakeTimers();
  vi.mocked(devicesApi.list).mockResolvedValueOnce([{ ...device, connection_status: 'online' }]).mockRejectedValueOnce(new Error('poll failed'));
  const view = render(<RemoteView />);
  await act(async () => { await Promise.resolve(); });
  expect(screen.getByText('组网状态：在线')).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(screen.queryByText('组网状态：在线')).toBeNull();
  expect(screen.getByRole('alert').textContent).toContain('poll failed');
  const calls = vi.mocked(devicesApi.list).mock.calls;
  const signal = calls[calls.length - 1][0];
  view.unmount();
  expect(signal?.aborted).toBe(true);
});

it('permits only direct unrevoked gateway choices and keeps synced host readonly', async () => {
  const router = { ...device, id: 'router', name: 'Router', source: 'netbird' as const, peer_id: 'p-router', connection_status: 'online' as const, access_mode: 'none' as const };
  vi.mocked(devicesApi.list).mockResolvedValue([device, router, { ...router, id: 'revoked', name: 'Old router', connection_status: 'revoked' }, { ...device, id: 'child', name: 'Other child', source: 'gateway', gateway_id: 'router' }]);
  vi.mocked(devicesApi.save).mockResolvedValue({ ...device, source: 'gateway', gateway_id: 'router' });
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'Router' });
  fireEvent.click(within(screen.getByRole('heading', { name: 'NAS' }).closest('article')!).getByRole('button', { name: '编辑' }));
  const choices = within(screen.getByLabelText('接入网关')).getAllByRole('option').map(option => option.getAttribute('value'));
  expect(choices).toEqual(['', 'router']);
  fireEvent.change(screen.getByLabelText('接入网关'), { target: { value: 'router' } });
  fireEvent.click(screen.getByRole('button', { name: '保存设备' }));
  await waitFor(() => expect(devicesApi.save).toHaveBeenCalledWith(expect.objectContaining({ gateway_id: 'router' }), 'one', expect.any(AbortSignal)));
  await waitFor(() => expect(screen.queryByRole('button', { name: '保存设备' })).toBeNull());
  fireEvent.click(within(screen.getByRole('heading', { name: 'Router' }).closest('article')!).getByRole('button', { name: '编辑' }));
  expect((screen.getByLabelText('主机名或 IP') as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText('接入网关') as HTMLSelectElement).disabled).toBe(true);
});

it('cancels stale polls and prevents repeated mutations from restoring an old device', async () => {
  vi.useFakeTimers();
  let resolvePoll!: (value: typeof device[]) => void;
  let resolveSave!: (value: typeof device) => void;
  vi.mocked(devicesApi.list).mockResolvedValueOnce([device]).mockImplementationOnce(() => new Promise(resolve => { resolvePoll = resolve; }));
  vi.mocked(devicesApi.save).mockImplementation(() => new Promise(resolve => { resolveSave = resolve; }));
  render(<RemoteView />);
  await act(async () => { await Promise.resolve(); });
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  fireEvent.click(screen.getByRole('button', { name: '编辑' }));
  fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'Renamed NAS' } });
  const save = screen.getByRole('button', { name: '保存设备' });
  fireEvent.click(save); fireEvent.click(save);
  expect(devicesApi.save).toHaveBeenCalledTimes(1);
  const staleSignal = vi.mocked(devicesApi.list).mock.calls[1][0];
  expect(staleSignal?.aborted).toBe(true);
  await act(async () => { resolveSave({ ...device, name: 'Renamed NAS' }); await Promise.resolve(); });
  await act(async () => { resolvePoll([device]); await Promise.resolve(); });
  expect(screen.getByRole('heading', { name: 'Renamed NAS' })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: 'NAS' })).toBeNull();
});

it('retains the revoked record and removes its remote access after a successful network revoke', async () => {
  const peer = { ...device, source: 'netbird' as const, peer_id: 'p', connection_status: 'online' as const, access_mode: 'ssh' as const };
  const revoked = { ...peer, connection_status: 'revoked' as const };
  vi.mocked(devicesApi.list).mockResolvedValueOnce([peer]).mockResolvedValue([revoked]);
  vi.mocked(devicesApi.revoke).mockResolvedValue(revoked);
  render(<RemoteView onSsh={vi.fn()} />);
  await screen.findByText('组网状态：在线');
  fireEvent.click(screen.getByRole('button', { name: '撤销入网' }));
  fireEvent.click(screen.getByRole('button', { name: '确认撤销入网' }));
  expect(await screen.findByText('组网状态：已撤销')).toBeTruthy();
  expect(screen.getByRole('heading', { name: 'NAS' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'SSH 连接' })).toBeNull();
});

it('clears a polling failure once a later snapshot succeeds', async () => {
  vi.useFakeTimers();
  vi.mocked(devicesApi.list).mockRejectedValueOnce(new Error('temporary outage')).mockResolvedValueOnce([device]);
  render(<RemoteView />);
  await act(async () => { await Promise.resolve(); });
  expect(screen.getByRole('alert').textContent).toContain('temporary outage');
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(screen.getByRole('heading', { name: 'NAS' })).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
});

it('stops the batch without launching later probes and keeps the UI usable', async () => {
  const targets = Array.from({ length: 6 }, (_, index) => ({ ...device, id: String(index), name: `Device ${index}` }));
  vi.mocked(devicesApi.list).mockResolvedValue(targets);
  vi.mocked(devicesApi.probe).mockImplementation((id, signal) => new Promise(resolve => signal?.addEventListener('abort', () => resolve(targets[Number(id)]))));
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'Device 5' });
  fireEvent.click(screen.getByRole('button', { name: '检测筛选结果 (6)' }));
  expect(devicesApi.probe).toHaveBeenCalledTimes(4);
  fireEvent.click(screen.getByRole('button', { name: '停止检测' }));
  expect(await screen.findByText('已停止后续检测：完成 0/6')).toBeTruthy();
  expect(devicesApi.probe).toHaveBeenCalledTimes(4);
  expect((screen.getByRole('button', { name: '添加设备' }) as HTMLButtonElement).disabled).toBe(false);
});

it('aborts an in-flight mutation and ignores its result after unmount', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([]);
  let resolveSave!: (value: typeof device) => void;
  vi.mocked(devicesApi.save).mockImplementation(() => new Promise(resolve => { resolveSave = resolve; }));
  const view = render(<RemoteView />);
  await screen.findByText(/尚未登记设备/);
  fireEvent.click(screen.getByRole('button', { name: '添加设备' }));
  fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'NAS' } });
  fireEvent.change(screen.getByLabelText('主机名或 IP'), { target: { value: '192.0.2.1' } });
  fireEvent.click(screen.getByRole('button', { name: '保存设备' }));
  const signal = vi.mocked(devicesApi.save).mock.calls[0][2];
  view.unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => { resolveSave(device); });
  expect(screen.queryByRole('heading', { name: 'NAS' })).toBeNull();
});

it('rejects invalid peer identities before sending an explicit link request', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([device]);
  vi.mocked(devicesApi.link).mockResolvedValue(device);
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'NAS' });
  fireEvent.click(screen.getByRole('button', { name: '关联组网节点' }));
  fireEvent.change(screen.getByLabelText('组网 peer ID'), { target: { value: '../peer' } });
  fireEvent.click(screen.getByRole('button', { name: '确认关联' }));
  expect((await screen.findByRole('alert')).textContent).toContain('peer ID');
  expect(devicesApi.link).not.toHaveBeenCalled();
});

it('requires clearing a gateway relationship before linking a child to a direct peer', async () => {
  const child = { ...device, source: 'gateway' as const, gateway_id: 'router' };
  vi.mocked(devicesApi.list).mockResolvedValue([child, { ...device, id: 'router', name: 'Router', source: 'netbird', peer_id: 'p-router' }]);
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'NAS' });
  const card = within(screen.getByRole('heading', { name: 'NAS' }).closest('article')!);
  expect(card.queryByRole('button', { name: '关联组网节点' })).toBeNull();
  expect(card.getByText(/先解除网关关联/)).toBeTruthy();
});

it('shows the selected revoked gateway and preserves its identity during an unrelated edit', async () => {
  const child = { ...device, source: 'gateway' as const, gateway_id: 'router', notes: 'Old note' };
  const router = { ...device, id: 'router', name: 'Revoked Router', source: 'netbird' as const, peer_id: 'p-router', connection_status: 'revoked' as const };
  vi.mocked(devicesApi.list).mockResolvedValue([child, router]);
  vi.mocked(devicesApi.save).mockResolvedValue({ ...child, notes: 'New note' });
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'NAS' });
  fireEvent.click(within(screen.getByRole('heading', { name: 'NAS' }).closest('article')!).getByRole('button', { name: '编辑' }));
  const select = screen.getByLabelText('接入网关') as HTMLSelectElement;
  expect(select.value).toBe('router');
  expect(select.selectedOptions[0].textContent).toContain('已撤销');
  expect(select.selectedOptions[0].disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('备注'), { target: { value: 'New note' } });
  fireEvent.click(screen.getByRole('button', { name: '保存设备' }));
  await waitFor(() => expect(devicesApi.save).toHaveBeenCalledWith(expect.objectContaining({ gateway_id: 'router', notes: 'New note' }), 'one', expect.any(AbortSignal)));
});

it('allows explicit removal when the current gateway is absent and no replacement is available', async () => {
  const child = { ...device, source: 'gateway' as const, gateway_id: 'missing-router' };
  vi.mocked(devicesApi.list).mockResolvedValue([child]);
  vi.mocked(devicesApi.save).mockResolvedValue({ ...device, gateway_id: null });
  render(<RemoteView />);
  await screen.findByRole('heading', { name: 'NAS' });
  fireEvent.click(screen.getByRole('button', { name: '编辑' }));
  const select = screen.getByLabelText('接入网关') as HTMLSelectElement;
  expect(select.value).toBe('missing-router');
  expect(select.selectedOptions[0].textContent).toContain('不可用');
  fireEvent.change(select, { target: { value: '' } });
  expect(select.value).toBe('');
  fireEvent.click(screen.getByRole('button', { name: '保存设备' }));
  await waitFor(() => expect(devicesApi.save).toHaveBeenCalledWith(expect.objectContaining({ gateway_id: null }), 'one', expect.any(AbortSignal)));
});

it('keeps one polling chain when an aborted poll finishes after a save and cannot restore stale online state', async () => {
  vi.useFakeTimers();
  const online = { ...device, connection_status: 'online' as const };
  let resolveAborted!: (value: typeof online[]) => void;
  let resolveNext!: (value: Array<typeof device & { connection_status: 'online' | 'offline' }>) => void;
  vi.mocked(devicesApi.list).mockResolvedValueOnce([online])
    .mockImplementationOnce(() => new Promise(resolve => { resolveAborted = resolve; }))
    .mockImplementationOnce(() => new Promise(resolve => { resolveNext = resolve; }))
    .mockResolvedValue([{ ...online, name: 'Renamed NAS' }]);
  vi.mocked(devicesApi.save).mockResolvedValue({ ...online, name: 'Renamed NAS' });
  render(<RemoteView />);
  await act(async () => { await Promise.resolve(); });
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  fireEvent.click(screen.getByRole('button', { name: '编辑' }));
  fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'Renamed NAS' } });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '保存设备' })); await Promise.resolve(); });
  expect(screen.getByRole('heading', { name: 'Renamed NAS' })).toBeTruthy();
  await act(async () => { resolveAborted([online]); await Promise.resolve(); });
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(devicesApi.list).toHaveBeenCalledTimes(3);
  await act(async () => { resolveNext([{ ...device, name: 'Renamed NAS', connection_status: 'offline' }]); await Promise.resolve(); });
  expect(screen.getByText('组网状态：离线')).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(4999); });
  expect(devicesApi.list).toHaveBeenCalledTimes(3);
  expect(screen.queryByText('组网状态：在线')).toBeNull();
});
