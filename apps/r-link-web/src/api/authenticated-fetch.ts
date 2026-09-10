import { API_CONFIG } from './config';
import { supabase, supabaseConfigured } from '../utils/supabase/client';

export function apiOrigin(): string {
  return new URL(API_CONFIG.baseURL || '/', window.location.href).origin;
}

/** Only the configured API origin may receive the user's access token. */
export async function authenticatedFetch(input: string | URL, init: RequestInit = {}): Promise<Response> {
  const url = new URL(input, window.location.href);
  if (url.origin !== apiOrigin()) throw new Error('拒绝向未配置的服务发送登录令牌');
  if (!supabaseConfigured) throw new Error('请先配置登录服务');
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  if (!data.session?.access_token) throw new Error('请先登录');
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${data.session.access_token}`);
  // Do not forward credentials through a server-provided redirect.
  const response = await fetch(url.toString(), { ...init, headers, redirect: 'error' });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(typeof payload?.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
  }
  return response;
}
