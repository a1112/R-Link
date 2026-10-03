import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { getServiceKey } from './api/service-access';
vi.mock('./components/DashboardView', () => ({ DashboardView: () => <p>Local dashboard</p> }));
vi.mock('./components/PluginsView', () => ({ PluginsView: () => <p>Plugins</p> }));
vi.mock('./components/TopologyView', () => ({ TopologyView: () => <p>Topology</p> }));
vi.mock('./components/pages/SSHView', () => ({ default: () => <input aria-label="SSH session marker" defaultValue="" /> }));
import App from './App';

afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); });

it('offers the R-File service page alongside the existing shared files page', () => {
  render(<App />);
  expect(screen.getByRole('button', { name: 'R-File' })).toBeTruthy();
  expect(screen.getByRole('button', { name: '共享文件' })).toBeTruthy();
});

it('opens the dashboard immediately and offers service settings without an account flow', () => {
  render(<App />);
  expect(screen.getByText('Local dashboard')).toBeTruthy();
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
  fireEvent.click(screen.getByRole('button', { name: 'SSH 终端' }));
  const marker = await screen.findByRole('textbox', { name: 'SSH session marker' });
  fireEvent.change(marker, { target: { value: 'live-session' } });
  fireEvent.click(screen.getByRole('button', { name: '仪表盘' }));
  expect(screen.getByText('Local dashboard')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'SSH 终端' }));
  expect(screen.getByRole('textbox', { name: 'SSH session marker' })).toBe(marker);
  expect((marker as HTMLInputElement).value).toBe('live-session');
});

it('discards a background SSH session when the operator changes the service origin', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'SSH 终端' }));
  const previous = await screen.findByRole('textbox', { name: 'SSH session marker' });
  fireEvent.change(previous, { target: { value: 'old-server-session' } });
  fireEvent.click(screen.getByRole('button', { name: '仪表盘' }));
  fireEvent.click(screen.getByRole('button', { name: '系统设置' }));
  fireEvent.click(screen.getByRole('button', { name: '服务访问' }));
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: 'https://other.example.test' } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(screen.queryByRole('textbox', { name: 'SSH session marker', hidden: true })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '关闭设置' }));
  fireEvent.click(screen.getByRole('button', { name: 'SSH 终端' }));
  const current = await screen.findByRole('textbox', { name: 'SSH session marker' });
  expect(current).not.toBe(previous);
  expect((current as HTMLInputElement).value).toBe('');
});
