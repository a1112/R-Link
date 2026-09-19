import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { openSshSocket } from '../../api/ssh-socket';
import { WebTerminal } from './Terminal';
vi.mock('../../api/ssh-socket', () => ({ openSshSocket: vi.fn() }));
vi.mock('xterm', () => ({ Terminal: class {
  cols = 80; rows = 24;
  open() {} loadAddon() {} onData() {} onResize() {} writeln() {} dispose() {}
} }));
vi.mock('xterm-addon-fit', () => ({ FitAddon: class { fit() {} } }));
vi.mock('xterm-addon-web-links', () => ({ WebLinksAddon: class {} }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });
it('does not silently reconnect a disconnected session when parent callbacks change', async () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  const socket = { readyState: 1, close: vi.fn(), send: vi.fn() };
  vi.mocked(openSshSocket).mockResolvedValue(socket as unknown as WebSocket);
  const props = { wsUrl: 'ws://localhost/api/ssh/connect', host: 'localhost', port: 22, username: 'test', password: 'fixture', autoConnect: true };
  const { rerender } = render(<WebTerminal {...props} onConnected={() => undefined} />);
  await waitFor(() => expect(openSshSocket).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: '断开' }));
  expect(socket.close).toHaveBeenCalledOnce();
  await act(async () => { rerender(<WebTerminal {...props} onConnected={() => undefined} />); });
  expect(openSshSocket).toHaveBeenCalledTimes(1);
  expect(screen.getByText('未连接')).toBeTruthy();
});
