import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
const post = vi.hoisted(() => vi.fn());
vi.mock('./client', () => ({ http: { post } }));
vi.mock('./config', () => ({ API_CONFIG: { baseURL: 'https://api.example.test' } }));
vi.mock('./authenticated-fetch', () => ({ apiOrigin: () => 'https://api.example.test' }));
import { openSshSocket, sshSocketUrl } from './ssh-socket';

describe('SSH websocket authentication', () => {
  const close = vi.fn();
  beforeEach(() => {
    post.mockReset().mockResolvedValue({ token: 'short-lived-ticket', scope: 'ssh' });
    close.mockClear();
    vi.stubGlobal('WebSocket', vi.fn(function () { return { close, addEventListener: vi.fn() }; }));
  });
  afterEach(() => vi.unstubAllGlobals());
  it('uses the configured API host and a scoped subprotocol ticket', async () => {
    expect(sshSocketUrl()).toBe('wss://api.example.test/api/ssh/connect');
    const controller = new AbortController();
    await openSshSocket(new URL(sshSocketUrl()), controller.signal);
    expect(post).toHaveBeenCalledWith('/api/auth/ws-token', undefined, { signal: controller.signal });
    expect(WebSocket).toHaveBeenCalledWith(sshSocketUrl(), ['r-link.ssh', 'r-link.ssh-token.short-lived-ticket']);
    controller.abort();
    expect(close).toHaveBeenCalledOnce();
  });
  it('never opens a socket when unmounted while the ticket is pending', async () => {
    let resolve!: (value: unknown) => void;
    post.mockImplementation(() => new Promise(done => { resolve = done; }));
    const controller = new AbortController();
    const pending = openSshSocket(new URL(sshSocketUrl()), controller.signal);
    controller.abort();
    resolve({ token: 'ticket', scope: 'ssh' });
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    expect(WebSocket).not.toHaveBeenCalled();
  });
  it('does not send tickets to another websocket origin', async () => {
    await expect(openSshSocket(new URL('wss://other.example/connect'), new AbortController().signal)).rejects.toThrow('不一致');
    expect(post).not.toHaveBeenCalled();
  });
  it('rejects a ticket issued for another scope', async () => {
    post.mockResolvedValue({ token: 'ticket', scope: 'console' });
    await expect(openSshSocket(new URL(sshSocketUrl()), new AbortController().signal)).rejects.toThrow('无效');
    expect(WebSocket).not.toHaveBeenCalled();
  });
});
