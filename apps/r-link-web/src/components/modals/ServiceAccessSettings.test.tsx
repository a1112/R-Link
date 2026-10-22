import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ServiceAccessSettings } from './ServiceAccessSettings';
import { http } from '../../api/client';
import { apiOrigin, getServiceKey, setServiceKey } from '../../api/service-access';
import { sshSocketUrl } from '../../api/ssh-socket';
import { updateAccount } from '../../api/account-access';
const legacy = () => updateAccount({ status: 'ready', config: { mode: 'service', login_enabled: false, desktop_login_enabled: false }, session: null, error: '' });

beforeEach(() => {
  localStorage.clear(); sessionStorage.clear();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
});
afterEach(() => { cleanup(); localStorage.clear(); sessionStorage.clear(); vi.unstubAllGlobals(); });

it('saves a cloud address for existing HTTP and SSH clients with an origin-scoped key', async () => {
  render(<ServiceAccessSettings />);
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: 'https://cloud.example.test/' } });
  fireEvent.change(screen.getByLabelText('服务访问密钥'), { target: { value: 'cloud-private' } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(apiOrigin()).toBe('https://cloud.example.test');
  legacy();
  await http.get('/api/devices');
  expect(fetch).toHaveBeenCalledWith('https://cloud.example.test/api/devices', expect.any(Object));
  expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer cloud-private');
  expect(sshSocketUrl()).toBe('wss://cloud.example.test/api/ssh/connect');
  cleanup(); render(<ServiceAccessSettings />);
  expect((screen.getByLabelText('服务地址') as HTMLInputElement).value).toBe('https://cloud.example.test');
});

it('does not copy the previous server key when changing the service address', async () => {
  setServiceKey('local-private');
  render(<ServiceAccessSettings />);
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: 'https://other.example.test' } });
  expect((screen.getByLabelText('服务访问密钥') as HTMLInputElement).value).toBe('');
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(getServiceKey()).toBe('');
  legacy();
  await http.get('/api/devices');
  expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).has('Authorization')).toBe(false);
});

it.each(['http://remote.example.test', 'https://user:password@cloud.example.test', 'https://cloud.example.test/a%2Fb', 'https://cloud.example.test?token=secret', 'javascript:alert(1)'])('rejects an unsafe service address %s before changing active requests', address => {
  const previous = apiOrigin();
  render(<ServiceAccessSettings />);
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: address } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(screen.getByRole('alert')).toBeTruthy();
  expect(apiOrigin()).toBe(previous);
  expect(fetch).not.toHaveBeenCalled();
});

it('supports a deployed service path and scopes HTTP and SSH requests to it', async () => {
  render(<ServiceAccessSettings />);
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: 'https://175.178.16.90/r-link/' } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  legacy(); await http.get('/api/devices');
  expect(fetch).toHaveBeenCalledWith('https://175.178.16.90/r-link/api/devices', expect.any(Object));
  expect(sshSocketUrl()).toBe('wss://175.178.16.90/r-link/api/ssh/connect');
});

it('allows explicit loopback HTTP and clearing the address to restore the default', () => {
  const previous = apiOrigin();
  render(<ServiceAccessSettings />);
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: 'http://127.0.0.1:8210' } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(apiOrigin()).toBe('http://127.0.0.1:8210');
  fireEvent.change(screen.getByLabelText('服务地址'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: '保存连接' }));
  expect(apiOrigin()).toBe(previous);
});
