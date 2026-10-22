import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const qosMocks = vi.hoisted(() => ({
  status: vi.fn(),
  saveConfig: vi.fn(),
  apply: vi.fn(),
  removeApplied: vi.fn(),
}));
const deviceMocks = vi.hoisted(() => ({ list: vi.fn() }));

vi.mock('../api/qos', async () => {
  const actual = await vi.importActual<typeof import('../api/qos')>('../api/qos');
  return { ...actual, qosApi: qosMocks };
});
vi.mock('../api/devices', () => ({ devicesApi: deviceMocks }));

import type { Device } from '../api/devices';
import type { QoSConfig, QoSStatus } from '../api/qos';
import { QosManager } from './QosManager';

afterEach(cleanup);

const config: QoSConfig = {
  interface: 'eth0',
  upload_mbps: 100,
  download_mbps: 200,
  policies: [{
    id: 'phone-1',
    label: 'Phone',
    device_id: null,
    ip: '192.168.1.20',
    enabled: true,
    upload_mbps: 20,
    download_mbps: 50,
    guaranteed_upload_mbps: 0.1,
    guaranteed_download_mbps: 0.1,
    priority: 3,
  }],
};

const devices: Device[] = [
  { id: 'host-device', name: '主机名设备', host: 'router.lan', port: 22, username: 'user', revision: 1, status: 'unchecked', checked_at: null, latency_ms: null },
  { id: 'ip-device', name: 'IP 设备', host: '192.168.1.40', port: 22, username: 'user', revision: 1, status: 'unchecked', checked_at: null, latency_ms: null },
];

function makeStatus(overrides: Partial<QoSStatus> = {}): QoSStatus {
  return {
    capabilities: { available: true, platform: 'linux', reason: null, interfaces: [{ name: 'eth0' }], backend: 'linux-tc-htb-ifb' },
    desired: { revision: 1, config },
    applied: null,
    state: 'inactive',
    error: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  deviceMocks.list.mockResolvedValue(devices);
  qosMocks.status.mockResolvedValue(makeStatus());
  qosMocks.saveConfig.mockResolvedValue(makeStatus({ desired: { revision: 2, config } }));
  qosMocks.apply.mockResolvedValue(makeStatus({ state: 'active', applied: { revision: 1, config } }));
  qosMocks.removeApplied.mockResolvedValue(makeStatus());
});

it('can save an unavailable environment while keeping apply disabled', async () => {
  qosMocks.status.mockResolvedValue(makeStatus({
    capabilities: { available: false, platform: 'darwin', reason: '需要 Linux 网关', interfaces: [], backend: 'linux-tc-htb-ifb' },
    state: 'unavailable',
  }));
  qosMocks.saveConfig.mockResolvedValue(makeStatus({
    capabilities: { available: false, platform: 'darwin', reason: '需要 Linux 网关', interfaces: [], backend: 'linux-tc-htb-ifb' },
    state: 'unavailable',
    desired: { revision: 2, config: { ...config, policies: [{ ...config.policies[0], label: 'Edited' }] } },
  }));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByLabelText('策略名称 1')).toBeTruthy());
  fireEvent.change(screen.getByLabelText('策略名称 1'), { target: { value: 'Edited' } });
  fireEvent.click(screen.getByRole('button', { name: '保存策略' }));
  await waitFor(() => expect(qosMocks.saveConfig).toHaveBeenCalledWith(1, expect.objectContaining({ interface: 'eth0' })));
  expect((screen.getByRole('button', { name: '应用到服务端' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/可以保存策略草稿/)).toBeTruthy();
});

it('does not resolve a hostname when choosing a device, but fills literal IPs', async () => {
  render(<QosManager />);
  await waitFor(() => expect(screen.getByLabelText('绑定设备 1')).toBeTruthy());
  const deviceSelect = screen.getByLabelText('绑定设备 1');
  const ipInput = screen.getByLabelText('来源 IP 1') as HTMLInputElement;
  fireEvent.change(deviceSelect, { target: { value: 'host-device' } });
  expect(ipInput.value).toBe('');
  expect(screen.getByText(/不会自动解析/)).toBeTruthy();
  fireEvent.change(deviceSelect, { target: { value: 'ip-device' } });
  expect(ipInput.value).toBe('192.168.1.40');
});

it('guards apply while the draft is unsaved', async () => {
  render(<QosManager />);
  await waitFor(() => expect(screen.getByLabelText('策略名称 1')).toBeTruthy());
  fireEvent.change(screen.getByLabelText('策略名称 1'), { target: { value: 'Changed' } });
  fireEvent.click(screen.getByRole('button', { name: '应用到服务端' }));
  expect(qosMocks.apply).not.toHaveBeenCalled();
  expect(screen.getByRole('alert').textContent).toContain('未保存修改');
});

it('requires explicit confirmation before applying a saved strategy', async () => {
  render(<QosManager />);
  await waitFor(() => expect(screen.getByRole('button', { name: '应用到服务端' })).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: '应用到服务端' }));
  expect(qosMocks.apply).not.toHaveBeenCalled();
  expect(screen.getByRole('dialog', { name: '确认应用 QoS 策略' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '确认应用' }));
  await waitFor(() => expect(qosMocks.apply).toHaveBeenCalledWith(1));
});

it('reports a revision conflict and keeps the edited draft', async () => {
  qosMocks.status.mockResolvedValueOnce(makeStatus()).mockResolvedValue(makeStatus({
    desired: { revision: 2, config: { ...config, policies: [{ ...config.policies[0], label: 'Server latest' }] } },
  }));
  qosMocks.saveConfig.mockRejectedValueOnce(new Error('HTTP 409: Conflict')).mockResolvedValue(makeStatus({ desired: { revision: 3, config: { ...config, policies: [{ ...config.policies[0], label: 'Changed' }] } } }));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByLabelText('策略名称 1')).toBeTruthy());
  fireEvent.change(screen.getByLabelText('策略名称 1'), { target: { value: 'Changed' } });
  fireEvent.click(screen.getByRole('button', { name: '保存策略' }));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('409'));
  expect((screen.getByLabelText('策略名称 1') as HTMLInputElement).value).toBe('Changed');
  const rebase = screen.getByRole('button', { name: '以最新保存版本为基础继续保存' });
  expect(rebase).toBeTruthy();
  fireEvent.click(rebase);
  fireEvent.click(screen.getByRole('button', { name: '保存策略' }));
  await waitFor(() => expect(qosMocks.saveConfig).toHaveBeenNthCalledWith(2, 2, expect.objectContaining({ policies: [expect.objectContaining({ label: 'Changed' })] })));
});

it('cancels an open apply confirmation when the saved revision changes', async () => {
  qosMocks.status.mockResolvedValueOnce(makeStatus()).mockResolvedValue(makeStatus({
    desired: { revision: 2, config: { ...config, policies: [{ ...config.policies[0], label: 'Server latest' }] } },
  }));
  vi.useFakeTimers();
  try {
    render(<QosManager />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    fireEvent.click(screen.getByRole('button', { name: '应用到服务端' }));
    expect(screen.getByRole('dialog', { name: '确认应用 QoS 策略' })).toBeTruthy();
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); await Promise.resolve(); });
    expect(screen.queryByRole('dialog', { name: '确认应用 QoS 策略' })).toBeNull();
    expect(qosMocks.apply).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toContain('原应用确认已取消');
  } finally {
    vi.useRealTimers();
  }
});

it('disables form controls while a save is in flight', async () => {
  let resolveSave: ((value: QoSStatus) => void) | undefined;
  qosMocks.saveConfig.mockImplementation(() => new Promise<QoSStatus>(resolve => { resolveSave = resolve; }));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByLabelText('策略名称 1')).toBeTruthy());
  fireEvent.change(screen.getByLabelText('策略名称 1'), { target: { value: 'Busy edit' } });
  fireEvent.click(screen.getByRole('button', { name: '保存策略' }));
  await waitFor(() => expect(screen.getByLabelText('策略名称 1').closest('fieldset')?.hasAttribute('disabled')).toBe(true));
  resolveSave?.(makeStatus({ desired: { revision: 2, config: { ...config, policies: [{ ...config.policies[0], label: 'Busy edit' }] } } }));
  await waitFor(() => expect(screen.getByLabelText('策略名称 1').closest('fieldset')?.hasAttribute('disabled')).toBe(false));
});

it('ignores a late status response from before a mutation began', async () => {
  let resolveLateStatus: ((value: QoSStatus) => void) | undefined;
  qosMocks.status.mockResolvedValueOnce(makeStatus()).mockImplementationOnce(() => new Promise<QoSStatus>(resolve => { resolveLateStatus = resolve; }));
  qosMocks.saveConfig.mockResolvedValue(makeStatus({
    state: 'pending',
    desired: { revision: 2, config: { ...config, policies: [{ ...config.policies[0], label: 'Changed' }] } },
  }));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByLabelText('策略名称 1')).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: '刷新 QoS 状态' }));
  fireEvent.change(screen.getByLabelText('策略名称 1'), { target: { value: 'Changed' } });
  fireEvent.click(screen.getByRole('button', { name: '保存策略' }));
  await waitFor(() => expect(qosMocks.saveConfig).toHaveBeenCalled());
  resolveLateStatus?.(makeStatus({ state: 'inactive', desired: { revision: 1, config } }));
  await waitFor(() => expect(screen.getByText('已保存，等待应用')).toBeTruthy());
});

it('marks an applied record unverified when the environment is unavailable', async () => {
  qosMocks.status.mockResolvedValue(makeStatus({
    capabilities: { available: false, platform: 'darwin', reason: '需要 Linux 网关', interfaces: [], backend: 'linux-tc-htb-ifb' },
    applied: { revision: 1, config },
    state: 'unavailable',
  }));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByText('#1（记录，未核验）')).toBeTruthy());
  expect(screen.queryByText('#1（已核验）')).toBeNull();
});

it('captures the applied revision before confirming disable', async () => {
  qosMocks.status.mockResolvedValue(makeStatus({
    applied: { revision: 4, config },
    state: 'active',
  }));
  qosMocks.removeApplied.mockResolvedValue(makeStatus({ applied: null, state: 'pending' }));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByRole('button', { name: '停用已应用限速' })).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: '停用已应用限速' }));
  expect(screen.getByRole('dialog', { name: '确认停用 QoS 限速' }).textContent).toContain('#4');
  fireEvent.click(screen.getByRole('button', { name: '确认停用' }));
  await waitFor(() => expect(qosMocks.removeApplied).toHaveBeenCalledWith(4));
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('已停用服务端限速'));
  expect(screen.queryByRole('alert')).toBeNull();
});

it('offers cleanup for an incomplete applied revision', async () => {
  qosMocks.status.mockResolvedValue(makeStatus({
    applied: null,
    cleanup_revision: 6,
    state: 'error',
    error: '清理未完成',
  }));
  qosMocks.removeApplied.mockResolvedValue(makeStatus({ applied: null, cleanup_revision: null, state: 'inactive' }));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByRole('button', { name: '完成未清理限速' })).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: '完成未清理限速' }));
  expect(screen.getByRole('dialog', { name: '确认停用 QoS 限速' }).textContent).toContain('记录版本 #6');
  fireEvent.click(screen.getByRole('button', { name: '确认完成清理' }));
  await waitFor(() => expect(qosMocks.removeApplied).toHaveBeenCalledWith(6));
});

it('cancels disable confirmation when the cleanup revision changes', async () => {
  qosMocks.status.mockResolvedValueOnce(makeStatus({
    applied: { revision: 4, config },
    state: 'active',
  })).mockResolvedValue(makeStatus({
    applied: { revision: 5, config },
    state: 'active',
  }));
  vi.useFakeTimers();
  try {
    render(<QosManager />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    fireEvent.click(screen.getByRole('button', { name: '停用已应用限速' }));
    expect((screen.getByRole('button', { name: '刷新 QoS 状态' }) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => { vi.advanceTimersByTime(5000); await Promise.resolve(); await Promise.resolve(); });
    expect(screen.queryByRole('dialog', { name: '确认停用 QoS 限速' })).toBeNull();
    expect(qosMocks.removeApplied).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toContain('原停用确认已取消');
  } finally {
    vi.useRealTimers();
  }
});

it('reports a cleanup failure without claiming that limits were disabled', async () => {
  qosMocks.status.mockResolvedValue(makeStatus({
    applied: { revision: 4, config },
    state: 'active',
  }));
  qosMocks.removeApplied.mockRejectedValue(new Error('HTTP 502: Bad Gateway'));
  render(<QosManager />);
  await waitFor(() => expect(screen.getByRole('button', { name: '停用已应用限速' })).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: '停用已应用限速' }));
  fireEvent.click(screen.getByRole('button', { name: '确认停用' }));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('502'));
  expect(screen.queryByText('已停用服务端限速，保存的策略记录仍保留。')).toBeNull();
});

