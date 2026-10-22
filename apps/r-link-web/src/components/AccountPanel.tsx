import { useState } from 'react';
import type { AccountState } from '../api/account-access';
import { serviceEndpoint } from '../api/account-access';

export const roleLabels = { pending: '等待审批', viewer: '只读成员', operator: '操作员', admin: '管理员' };
export type AccountActions = { account: AccountState; beginLogin: () => Promise<void>; logout: () => Promise<void>; refresh: () => Promise<void>; cancelLogin: () => void };

export function AccountControl({ actions }: { actions: AccountActions }) {
  const { account } = actions;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (account.config?.mode !== 'oidc') return null;
  const user = account.session?.user;
  const run = async (operation: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setError('');
    try { await operation(); }
    catch (error) { if (!(error instanceof DOMException && error.name === 'AbortError')) setError(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };
  return <div className="flex items-center gap-2 text-xs relative">
    {user && account.session?.authenticated ? <>
      <span className="max-w-48 truncate" title={user.email || user.display_name}>{user.display_name || user.email || '账户'} · {roleLabels[user.role]}</span>
      <button disabled={busy} onClick={() => void run(actions.logout)} className="rounded border border-[var(--c-700)] px-3 py-1.5 disabled:opacity-50">退出账户</button>
    </> : <button disabled={busy || !account.config.login_enabled} onClick={() => void run(actions.beginLogin)} className="rounded bg-blue-600 px-3 py-1.5 text-white disabled:opacity-50">{busy ? '等待浏览器登录…' : '账户登录'}</button>}
    {busy && !user && <button onClick={() => { actions.cancelLogin(); setBusy(false); }} className="rounded border px-2 py-1.5">取消登录</button>}
    {error && <span role="alert" className="absolute top-full right-0 mt-2 w-72 rounded border border-red-500/40 bg-[var(--c-950)] p-3 text-red-400 z-30">{error}</span>}
  </div>;
}

export function AccountGate({ actions }: { actions: AccountActions }) {
  const { account } = actions;
  const user = account.session?.user;
  if (account.status === 'loading') return <p role="status" className="p-6">正在连接服务…</p>;
  if (account.status === 'error') return <section className="p-6 space-y-4"><h2 className="text-lg font-semibold">无法连接服务</h2><p role="alert">{account.error}</p><button className="rounded border px-4 py-2" onClick={() => void actions.refresh()}>重试连接</button><p className="text-sm text-[var(--c-400)]">可以在系统设置中检查服务地址。</p></section>;
  if (user && account.session?.authenticated) return <section className="p-6 space-y-4"><h2 className="text-xl font-semibold">{user.disabled ? '账户已停用' : '等待管理员批准'}</h2><p>当前账户：{user.display_name || user.email || user.id}</p><p className="text-sm text-[var(--c-400)]">{user.disabled ? '请联系管理员恢复访问。' : '登录成功。管理员批准并分配角色后，即可查看共享设备和组网资源。'}</p><button className="rounded border px-4 py-2" onClick={() => void actions.refresh()}>刷新权限</button></section>;
  return <section className="p-6 space-y-4 max-w-xl"><h2 className="text-xl font-semibold">登录 R-Link</h2><p className="text-sm text-[var(--c-400)]">使用统一账户登录。设备和虚拟网络由服务成员共享，操作权限由管理员分配。</p>{account.config?.login_enabled ? <AccountControl actions={actions} /> : <p role="alert">服务端账户登录尚未配置完成，请联系管理员。</p>}{new URL(serviceEndpoint('/')).origin !== window.location.origin && !('__TAURI_INTERNALS__' in window) && <a className="text-blue-400 underline" href={serviceEndpoint('/')} rel="noreferrer">打开服务网页</a>}</section>;
}
