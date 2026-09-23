import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { meshApi } from '../../api/mesh';
vi.mock('../../api/mesh', () => ({ meshApi: {
  status: vi.fn(), peers: vi.fn(), groups: vi.fn(), keys: vi.fn(), policies: vi.fn(), networks: vi.fn(),
  createKey: vi.fn(), saveGroup: vi.fn(), renamePeer: vi.fn(), deletePeer: vi.fn(),
  resources: vi.fn(), routers: vi.fn(), saveResource: vi.fn(), saveRouter: vi.fn(),
} }));
import { MeshView } from './MeshView';

const connected = { id: 'peer01', name: 'NAS', ip: '100.64.1.1', ipv6: null, connected: true, last_seen: null, os: 'Windows', groups: [{ id: 'group01', name: 'office' }] };
const disconnected = { ...connected, id: 'peer02', name: 'Laptop', ip: '100.64.1.2', connected: false };
beforeEach(() => {
  vi.mocked(meshApi.status).mockResolvedValue({ configured: true, reachable: true, management_url: 'https://mesh.example.com', peers: 2, connected: 1, reason: null });
  vi.mocked(meshApi.peers).mockResolvedValue([connected, disconnected]);
  vi.mocked(meshApi.groups).mockResolvedValue([{ id: 'group01', name: 'office', peers_count: 1, peers: [{ id: 'peer01', name: 'NAS' }] }]);
  vi.mocked(meshApi.keys).mockResolvedValue([]);
  vi.mocked(meshApi.policies).mockResolvedValue([]);
  vi.mocked(meshApi.networks).mockResolvedValue([]);
  vi.mocked(meshApi.resources).mockResolvedValue([]);
  vi.mocked(meshApi.routers).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('does not present a fabricated virtual network when management is unconfigured', async () => {
  vi.mocked(meshApi.status).mockResolvedValue({ configured: false, reachable: false, peers: 0, connected: 0, reason: '请配置服务' });
  render(<MeshView />);
  expect(await screen.findByText(/请配置服务/)).toBeTruthy();
  expect(meshApi.peers).not.toHaveBeenCalled();
  expect(screen.queryByText('NAS')).toBeNull();
});

it('shows NetBird peer state and edits group membership through its API', async () => {
  render(<MeshView />);
  await screen.findByText('NAS');
  expect(screen.getByText('100.64.1.1', { exact: false })).toBeTruthy();
  expect(screen.getByText('管理端在线')).toBeTruthy();
  expect(screen.getByText('离线')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '分组' }));
  fireEvent.click(await screen.findByRole('button', { name: '编辑成员' }));
  fireEvent.click(screen.getByLabelText('Laptop'));
  fireEvent.click(screen.getByRole('button', { name: '保存分组' }));
  await waitFor(() => expect(meshApi.saveGroup).toHaveBeenCalledWith('office', ['peer01', 'peer02'], 'group01'));
});

it('shows a setup key once and clears it on dismissal', async () => {
  vi.mocked(meshApi.createKey).mockResolvedValue({ id: 1, name: 'new', type: 'one-off', valid: true, revoked: false, expires: '', used_times: 0, auto_groups: ['group01'], key: 'SECRET-ONCE' });
  render(<MeshView />);
  await screen.findByText('NAS');
  fireEvent.click(screen.getByRole('button', { name: '入网密钥' }));
  fireEvent.change(screen.getByLabelText('密钥名称'), { target: { value: 'new' } });
  fireEvent.change(screen.getByLabelText('自动加入分组'), { target: { value: 'group01' } });
  fireEvent.click(screen.getByRole('button', { name: '创建入网密钥' }));
  expect(await screen.findByText('SECRET-ONCE')).toBeTruthy();
  expect(meshApi.createKey).toHaveBeenCalledWith('new', 'group01', false);
  fireEvent.click(screen.getByRole('button', { name: '我已保存，关闭显示' }));
  expect(screen.queryByText('SECRET-ONCE')).toBeNull();
});

it('connects a network resource to a real NetBird network', async () => {
  vi.mocked(meshApi.networks).mockResolvedValue([{ id: 'network01', name: 'office-lan', description: '', routing_peers_count: 0 }]);
  render(<MeshView />);
  await screen.findByText('NAS');
  fireEvent.click(screen.getByRole('button', { name: '网络路由' }));
  fireEvent.click(screen.getByRole('button', { name: '查看资源与路由' }));
  await screen.findByText('暂无资源。');
  fireEvent.click(screen.getByRole('button', { name: '添加资源' }));
  fireEvent.change(screen.getByLabelText('资源名称'), { target: { value: 'LAN' } });
  fireEvent.change(screen.getByLabelText('地址或 CIDR'), { target: { value: '192.168.1.0/24' } });
  fireEvent.click(screen.getByLabelText('office'));
  fireEvent.click(screen.getByRole('button', { name: '保存资源' }));
  await waitFor(() => expect(meshApi.saveResource).toHaveBeenCalledWith('network01', expect.objectContaining({ address: '192.168.1.0/24', groups: ['group01'] }), undefined));
});
