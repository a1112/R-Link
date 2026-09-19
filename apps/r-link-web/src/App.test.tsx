import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { getServiceKey } from './api/service-access';
vi.mock('./components/DashboardView', () => ({ DashboardView: () => <p>Local dashboard</p> }));
vi.mock('./components/PluginsView', () => ({ PluginsView: () => <p>Plugins</p> }));
vi.mock('./components/TopologyView', () => ({ TopologyView: () => <p>Topology</p> }));
vi.mock('./components/pages/SSHView', () => ({ default: () => <input aria-label="SSH session marker" defaultValue="" /> }));
import App from './App';

afterEach(() => { cleanup(); sessionStorage.clear(); });

it('opens the dashboard immediately and offers service settings without an account flow', () => {
  render(<App />);
  expect(screen.getByText('Local dashboard')).toBeTruthy();
  expect(screen.queryByText('个人中心')).toBeNull();
  expect(screen.queryByText('登录')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '系统设置' }));
  fireEvent.click(screen.getByRole('button', { name: '服务访问' }));
  fireEvent.change(screen.getByLabelText('服务访问密钥'), { target: { value: 'service-key' } });
  fireEvent.click(screen.getByRole('button', { name: '保存密钥' }));
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
