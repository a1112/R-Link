import { apiOrigin, getServiceKey } from './service-access';
import { expireAccount, requestAccountAccess, serviceBase, trackAccountRequest } from './account-access';
export { apiOrigin } from './service-access';

/** OIDC uses its own session; legacy local/service access remains available. */
export async function authenticatedFetch(input: string | URL, init: RequestInit = {}): Promise<Response> {
  const url = new URL(input, window.location.href);
  if (url.origin !== apiOrigin()) throw new Error('拒绝向未配置的服务发送访问密钥');
  const headers = new Headers(init.headers);
  headers.delete('Authorization');
  headers.delete('X-R-Link-CSRF');
  headers.delete('X-R-Link-Session-Context');
  const access = requestAccountAccess();
  if (!access.ready || !access.mode) throw new Error('请先确认服务连接与账户状态');
  const base = new URL(`${serviceBase()}/`);
  if (!url.pathname.startsWith(base.pathname)) throw new Error('拒绝向服务路径之外发送凭据');
  let credentials: RequestCredentials = 'omit';
  if (access.mode === 'oidc') {
    if (!access.session?.authenticated || !access.session.user || access.session.user.disabled || access.session.user.role === 'pending') throw new Error('账户尚未获准访问服务');
    if (access.token) headers.set('Authorization', `Bearer ${access.token}`);
    else if (url.origin === window.location.origin) credentials = 'same-origin';
    else throw new Error('账户服务需要在服务网页或桌面客户端登录');
    if (!['GET', 'HEAD', 'OPTIONS'].includes((init.method || 'GET').toUpperCase())) {
      if (access.csrf) headers.set('X-R-Link-CSRF', access.csrf);
      if (access.context) headers.set('X-R-Link-Session-Context', access.context);
    }
  } else if (access.ready && (access.mode === 'local' || access.mode === 'service')) {
    const key = getServiceKey();
    if (key) headers.set('Authorization', `Bearer ${key}`);
  }
  const request = trackAccountRequest(init.signal);
  // Do not forward credentials through a server-provided redirect.
  try {
    const response = await fetch(url.toString(), { ...init, headers, signal: request.signal, credentials, redirect: 'error' });
    if (!request.isCurrent()) throw new DOMException('账户或服务已切换', 'AbortError');
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      if (!request.isCurrent()) throw new DOMException('账户或服务已切换', 'AbortError');
      if (access.mode === 'oidc' && [401, 409].includes(response.status)) expireAccount();
      if (access.mode === 'oidc' && response.status === 403) window.dispatchEvent(new Event('r-link-account-refresh'));
      throw new Error(typeof payload?.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
    }
    return response;
  } finally {
    request.done();
  }
}
