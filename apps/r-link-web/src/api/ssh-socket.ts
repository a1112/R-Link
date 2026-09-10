import { API_CONFIG } from './config';
import { apiOrigin } from './authenticated-fetch';
import { http } from './client';

export function sshSocketUrl(): string {
  const url = new URL(`${API_CONFIG.baseURL}/api/ssh/connect`, window.location.href);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}

export async function openSshSocket(url: URL, signal: AbortSignal): Promise<WebSocket> {
  const origin = new URL(apiOrigin());
  origin.protocol = origin.protocol === 'https:' ? 'wss:' : 'ws:';
  if (url.origin !== origin.origin) throw new Error('SSH 服务地址与 API 配置不一致');
  const ticket = await http.post<{ token: string; scope: string }>('/api/auth/ws-token', undefined, { signal });
  if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
  if (!ticket.token || ticket.scope !== 'ssh') throw new Error('SSH 登录票据无效');
  const socket = new WebSocket(url.toString(), ['r-link.ssh', `r-link.ssh-token.${ticket.token}`]);
  const close = () => socket.close();
  signal.addEventListener('abort', close, { once: true });
  socket.addEventListener('close', () => signal.removeEventListener('abort', close), { once: true });
  return socket;
}
