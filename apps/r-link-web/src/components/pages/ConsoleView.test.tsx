import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { http } from '../../api/client';
vi.mock('../../api/client', () => ({ http: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../../api/authenticated-fetch', () => ({ apiOrigin: () => 'http://127.0.0.1:8210' }));
import { ConsoleView, localConsoleUrl } from './ConsoleView';
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it.each([false, undefined])('does not claim startup succeeded for success=%s', async success => {
  vi.mocked(http.get).mockResolvedValue({ ttyd_running: false });
  vi.mocked(http.post).mockResolvedValue({ success, error: 'ttyd missing' });
  render(<ConsoleView />);
  fireEvent.click(await screen.findByRole('button', { name: '启动控制台' }));
  expect((await screen.findByRole('alert')).textContent).toContain('ttyd missing');
  expect(screen.queryByTitle('Web Console')).toBeNull();
  expect(screen.queryByText('控制台运行中')).toBeNull();
});
it('does not represent a failed status request as a stopped service', async () => {
  vi.mocked(http.get).mockRejectedValue(new Error('HTTP 503'));
  render(<ConsoleView />);
  expect((await screen.findByRole('alert')).textContent).toContain('HTTP 503');
  expect(screen.queryByText('控制台已停止')).toBeNull();
  expect(screen.queryByRole('button', { name: '启动控制台' })).toBeNull();
});
it('rejects unsafe and ambiguous iframe addresses', () => {
  expect(localConsoleUrl('javascript:alert(1)')).toBeNull();
  expect(localConsoleUrl('/console')).toBeNull();
  expect(localConsoleUrl('https://foreign.example')).toBeNull();
  expect(localConsoleUrl('http://user:pass@127.0.0.1:7681')).toBeNull();
  expect(localConsoleUrl('http://127.0.0.1:7681')).toBe('http://127.0.0.1:7681/');
});
