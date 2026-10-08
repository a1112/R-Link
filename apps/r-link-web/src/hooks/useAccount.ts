import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { accountsApi } from '../api/accounts';
import { expireAccount, getAccountState, resetAccount, serviceEndpoint, setDesktopSessionToken, subscribeAccount, updateAccount } from '../api/account-access';
import { isTauriRuntime } from '../utils/tauriWindow';

export const useAccountState = () => useSyncExternalStore(subscribeAccount, getAccountState);

export function useAccount() {
  const account = useAccountState();
  const revision = useRef(0);
  const discovery = useRef<AbortController>();
  const login = useRef<AbortController>();
  const sessionSuppressed = useRef(false);
  const refresh = useCallback(async () => {
    const generation = ++revision.current;
    discovery.current?.abort();
    const controller = new AbortController(); discovery.current = controller;
    try {
      const config = await accountsApi.config(controller.signal);
      if (controller.signal.aborted || generation !== revision.current) return;
      // Set the mode before session discovery so an existing desktop session can be used.
      updateAccount({ ...getAccountState(), status: getAccountState().status === 'ready' ? 'ready' : 'loading', config, error: '' });
      const session = config.mode === 'oidc' ? (sessionSuppressed.current
        ? { authenticated: false, mode: 'oidc' as const, user: null, csrf_token: null, expires_at: null, session_context: null }
        : await accountsApi.session(controller.signal)) : null;
      if (controller.signal.aborted || generation !== revision.current) return;
      if (session && (session.mode !== 'oidc' || typeof session.authenticated !== 'boolean' || (session.authenticated && (!session.user || !['pending', 'viewer', 'operator', 'admin'].includes(session.user.role))))) throw new Error('服务未返回有效的账户会话');
      if (!session?.authenticated) setDesktopSessionToken('');
      updateAccount({ status: 'ready', config, session, error: '' });
    } catch (error) {
      if (controller.signal.aborted || generation !== revision.current) return;
      setDesktopSessionToken('');
      updateAccount({ status: 'error', config: getAccountState().config, session: null, error: error instanceof Error ? error.message : String(error) });
    }
  }, []);

  useEffect(() => {
    const changed = () => { login.current?.abort(); discovery.current?.abort(); sessionSuppressed.current = false; resetAccount(); void refresh(); };
    const check = () => { if (document.visibilityState !== 'hidden') void refresh(); };
    void refresh();
    window.addEventListener('r-link-service-access-changed', changed);
    window.addEventListener('r-link-account-refresh', check);
    document.addEventListener('visibilitychange', check);
    const interval = setInterval(() => { if (getAccountState().config?.mode === 'oidc') check(); }, 45000);
    return () => {
      revision.current++; discovery.current?.abort(); login.current?.abort(); clearInterval(interval);
      window.removeEventListener('r-link-service-access-changed', changed);
      window.removeEventListener('r-link-account-refresh', check);
      document.removeEventListener('visibilitychange', check);
    };
  }, [refresh]);

  useEffect(() => {
    const expires = account.session?.expires_at;
    if (!expires || !account.session?.authenticated) return;
    const timeout = setTimeout(expireAccount, Math.max(0, expires * 1000 - Date.now()));
    return () => clearTimeout(timeout);
  }, [account.session?.expires_at, account.session?.authenticated]);

  const beginLogin = useCallback(async () => {
    if (!getAccountState().config?.login_enabled) throw new Error('服务端尚未配置账户登录');
    sessionSuppressed.current = false;
    if (!isTauriRuntime()) {
      const url = new URL(serviceEndpoint('/api/auth/login'));
      if (url.origin !== window.location.origin) throw new Error('请在服务网页中登录，或使用桌面客户端');
      window.location.assign(url.toString());
      return;
    }
    if (!getAccountState().config?.desktop_login_enabled) throw new Error('该服务尚未启用桌面登录');
    login.current?.abort();
    const controller = new AbortController(); login.current = controller;
    const flow = await accountsApi.desktopStart(controller.signal);
    if (controller.signal.aborted) return;
    if (!flow || typeof flow.login_url !== 'string' || typeof flow.flow_id !== 'string' || typeof flow.poll_secret !== 'string' || !flow.flow_id || !flow.poll_secret || !Number.isFinite(flow.expires_in) || flow.expires_in < 1 || flow.expires_in > 300) throw new Error('服务返回的桌面登录流程无效');
    const url = new URL(flow.login_url);
    const expected = new URL(serviceEndpoint('/api/auth/desktop/login'));
    if (url.protocol !== 'https:' || url.username || url.password || url.hash || url.origin !== expected.origin || url.pathname !== expected.pathname || url.searchParams.get('flow_id') !== flow.flow_id || [...url.searchParams.keys()].length !== 1) throw new Error('服务返回的桌面登录入口无效');
    if (controller.signal.aborted) return;
    await invoke('open_auth_login', { url: url.toString() });
    const deadline = Date.now() + Math.min(flow.expires_in, 300) * 1000;
    while (!controller.signal.aborted && Date.now() < deadline) {
      const response = await accountsApi.desktopExchange(flow.flow_id, flow.poll_secret, controller.signal);
      if (response.status === 200 && typeof response.value?.token === 'string' && response.value.token) {
        if (controller.signal.aborted) return;
        setDesktopSessionToken(response.value.token);
        await refresh();
        return;
      }
      if (response.status !== 202 || !response.value?.pending) throw new Error('桌面登录交换响应无效');
      await new Promise<void>((resolve, reject) => {
        const stop = () => { clearTimeout(timer); reject(new DOMException('已取消登录', 'AbortError')); };
        const timer = setTimeout(() => { controller.signal.removeEventListener('abort', stop); resolve(); }, 2000);
        controller.signal.addEventListener('abort', stop, { once: true });
        if (controller.signal.aborted) stop();
      });
    }
    if (!controller.signal.aborted) throw new Error('登录已过期，请重新登录');
  }, [refresh]);

  const logout = useCallback(async () => {
    sessionSuppressed.current = true;
    login.current?.abort(); discovery.current?.abort(); revision.current++;
    try { await accountsApi.logout(); }
    finally { expireAccount(); }
  }, []);

  const cancelLogin = useCallback(() => {
    sessionSuppressed.current = true;
    login.current?.abort(); discovery.current?.abort(); revision.current++;
    expireAccount();
  }, []);

  return { account, refresh, beginLogin, cancelLogin, logout };
}
