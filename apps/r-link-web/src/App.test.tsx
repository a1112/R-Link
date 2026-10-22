import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { getServiceKey } from './api/service-access';
import { accountsApi } from './api/accounts';
import { resetAccount, type AccountUser } from './api/account-access';
vi.mock('./api/accounts', () => ({ accountsApi: { config: vi.fn(), session: vi.fn(), logout: vi.fn(), users: vi.fn(), updateUser: vi.fn() } }));
vi.mock('./components/DashboardView', () => ({ DashboardView: () => <p>Local dashboard</p> }));
vi.mock('./components/PluginsView', () => ({ PluginsView: () => <p>Plugins</p> }));
vi.mock('./components/TopologyView', () => ({ TopologyView: () => <p>Topology</p> }));
vi.mock('./components/pages/SSHView', () => ({ default: () => <input aria-label="SSH session marker" defaultValue="" /> }));
import App from './App';

beforeEach(() => {
  vi.clearAllMocks();
  resetAccount();
  vi.mocked(accountsApi.config).mockResolvedValue({ mode: 'local', login_enabled: false, desktop_login_enabled: false });
  vi.mocked(accountsApi.session).mockResolvedValue({ authenticated: false, mode: 'local', user: null, csrf_token: null, expires_at: null });
  vi.mocked(accountsApi.logout).mockResolvedValue(undefined);
  vi.mocked(accountsApi.users).mockResolvedValue([]);
});
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); vi.unstubAllGlobals(); });

it('offers the R-File service page alongside the existing shared files page', async () => {
  render(<App />);
  expect(await screen.findByRole('button', { name: 'R-File' })).toBeTruthy();
  expect(screen.getByRole('button', { name: '共享文件' })).toBeTruthy();
});

it('opens topology after local configuration discovery and offers service settings without an account flow', async () => {
  render(<App />);
  expect(await screen.findByText('Topology')).toBeTruthy();
  expect(screen.getByRole('button', { name: '设备拓扑' }).getAttribute('aria-current')).toBe('page');
  expect(screen.queryByText('个人中心')).toBeNull();
  expect(screen.queryByText('登录')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '系统设置' }));
  fireEvent.click(screen.getByRole('button', { name: '服务访问' }));
  fireEvent.change(screen.getByLabelText('服务访问密钥'), { target: { value: 'service-key' } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(getServiceKey()).toBe('service-key');
  fireEvent.click(screen.getByRole('button', { name: '清除密钥' }));
  expect(getServiceKey()).toBe('');
});

it('preserves the mounted SSH session while navigating to another management page', async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'SSH 终端' }));
  const marker = await screen.findByRole('textbox', { name: 'SSH session marker' });
  fireEvent.change(marker, { target: { value: 'live-session' } });
  fireEvent.click(screen.getByRole('button', { name: '系统概览' }));
  expect(screen.getByText('Local dashboard')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'SSH 终端' }));
  expect(screen.getByRole('textbox', { name: 'SSH session marker' })).toBe(marker);
  expect((marker as HTMLInputElement).value).toBe('live-session');
});

it('discards a background SSH session when the operator changes the service origin', async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'SSH 终端' }));
  const previous = await screen.findByRole('textbox', { name: 'SSH session marker' });
  fireEvent.change(previous, { target: { value: 'old-server-session' } });
  fireEvent.click(screen.getByRole('button', { name: '设备拓扑' }));
  fireEvent.click(screen.getByRole('button', { name: '系统设置' }));
  fireEvent.click(screen.getByRole('button', { name: '服务访问' }));
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: 'https://other.example.test' } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(screen.queryByRole('textbox', { name: 'SSH session marker', hidden: true })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '关闭设置' }));
  fireEvent.click(await screen.findByRole('button', { name: 'SSH 终端' }));
  const current = await screen.findByRole('textbox', { name: 'SSH session marker' });
  expect(current).not.toBe(previous);
  expect((current as HTMLInputElement).value).toBe('');
});

const member = (role: AccountUser['role']): AccountUser => ({ id: 'member-1', issuer: 'https://auth.example.test/realms/r', subject: 'subject', display_name: 'Test Member', email: 'member@example.test', role, disabled: false });
function oidc(role?: AccountUser['role']) {
  vi.mocked(accountsApi.config).mockResolvedValue({ mode: 'oidc', login_enabled: true, desktop_login_enabled: true });
  vi.mocked(accountsApi.session).mockResolvedValue({ authenticated: !!role, mode: 'oidc', user: role ? member(role) : null, csrf_token: role ? 'csrf' : null, expires_at: null, session_context: role ? 'context' : null });
}

it('does not mount business pages for anonymous or pending accounts', async () => {
  oidc(); render(<App />);
  expect(await screen.findByText('登录 R-Link')).toBeTruthy();
  expect(screen.queryByText('Topology')).toBeNull();
  expect(screen.queryByRole('button', { name: 'SSH 终端' })).toBeNull();
  cleanup(); resetAccount(); oidc('pending'); render(<App />);
  expect(await screen.findByText('等待管理员批准')).toBeTruthy();
  expect(screen.queryByText('Topology')).toBeNull();
  expect(screen.queryByRole('button', { name: '设备管理' })).toBeNull();
});

it('shows only read-only endpoints and navigation to a viewer', async () => {
  oidc('viewer');
  const fetcher = vi.fn().mockResolvedValue(new Response('[]'));
  vi.stubGlobal('fetch', fetcher);
  render(<App />);
  expect(await screen.findByText('共享设备')).toBeTruthy();
  await waitFor(() => expect(fetcher).toHaveBeenCalled());
  expect(fetcher.mock.calls.map(([url]) => new URL(String(url)).pathname)).toEqual(['/api/devices']);
  expect(screen.queryByRole('button', { name: 'SSH 终端' })).toBeNull();
  expect(screen.queryByRole('button', { name: '插件中心' })).toBeNull();
  expect(screen.queryByRole('button', { name: '添加设备' })).toBeNull();
});

it('clears SSH and private page state when the same member gets a new session', async () => {
  oidc('admin'); render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'SSH 终端' }));
  const old = await screen.findByRole('textbox', { name: 'SSH session marker' });
  fireEvent.change(old, { target: { value: 'old-credentials' } });
  vi.mocked(accountsApi.session).mockResolvedValue({ authenticated: true, mode: 'oidc', user: member('admin'), csrf_token: 'new-csrf', expires_at: null, session_context: 'new-session' });
  await act(async () => { window.dispatchEvent(new Event('r-link-account-refresh')); });
  await waitFor(() => expect(screen.queryByRole('textbox', { name: 'SSH session marker', hidden: true })).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: 'SSH 终端' }));
  const current = await screen.findByRole('textbox', { name: 'SSH session marker' });
  expect(current).not.toBe(old); expect((current as HTMLInputElement).value).toBe('');
});

it('removes SSH immediately when a member is downgraded to pending', async () => {
  oidc('operator'); render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: 'SSH 终端' }));
  await screen.findByRole('textbox', { name: 'SSH session marker' });
  oidc('pending');
  await act(async () => { window.dispatchEvent(new Event('r-link-account-refresh')); });
  expect(await screen.findByText('等待管理员批准')).toBeTruthy();
  expect(screen.queryByRole('textbox', { name: 'SSH session marker', hidden: true })).toBeNull();
  expect(screen.queryByRole('button', { name: 'SSH 终端' })).toBeNull();
});

it('offers user approval controls only to administrators', async () => {
  oidc('admin'); render(<App />); await screen.findByText('Topology');
  fireEvent.click(screen.getByRole('button', { name: '系统设置' }));
  fireEvent.click(screen.getByRole('button', { name: '用户权限' }));
  await waitFor(() => expect(accountsApi.users).toHaveBeenCalled());
  cleanup(); resetAccount(); oidc('operator'); render(<App />); await screen.findByText('Topology');
  fireEvent.click(screen.getByRole('button', { name: '系统设置' }));
  expect(screen.queryByRole('button', { name: '用户权限' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Web 控制台' })).toBeNull();
  expect(screen.queryByRole('button', { name: '插件中心' })).toBeNull();
});

it('fails closed when account configuration cannot be discovered', async () => {
  vi.mocked(accountsApi.config).mockRejectedValue(new Error('服务不可达')); render(<App />);
  expect(await screen.findByText('无法连接服务')).toBeTruthy();
  expect(screen.queryByText('Topology')).toBeNull();
  expect(screen.queryByRole('button', { name: 'SSH 终端' })).toBeNull();
});
