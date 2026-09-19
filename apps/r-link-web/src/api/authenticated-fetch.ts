import { apiOrigin, getServiceKey } from './service-access';
export { apiOrigin } from './service-access';

/** Local requests need no cloud session; remote access uses an optional service key. */
export async function authenticatedFetch(input: string | URL, init: RequestInit = {}): Promise<Response> {
  const url = new URL(input, window.location.href);
  if (url.origin !== apiOrigin()) throw new Error('拒绝向未配置的服务发送访问密钥');
  const headers = new Headers(init.headers);
  headers.delete('Authorization');
  const key = getServiceKey();
  if (key) headers.set('Authorization', `Bearer ${key}`);
  // Do not forward credentials through a server-provided redirect.
  const response = await fetch(url.toString(), { ...init, headers, credentials: 'omit', redirect: 'error' });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(typeof payload?.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
  }
  return response;
}
