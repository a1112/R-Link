import { useCallback, useState } from 'react';
import { accountsApi } from '../../api/accounts';
import { getAccountState, isAccountAdmin, type AccountRole, type AccountUser } from '../../api/account-access';
import { usePolling } from '../../api/usePolling';
import { roleLabels } from '../AccountPanel';

const control = 'rounded border border-[var(--c-700)] bg-[var(--c-950)] px-3 py-2 disabled:opacity-50';

function UserRow({ user, onSaved }: { user: AccountUser; onSaved: () => Promise<void> }) {
  const [role, setRole] = useState(user.role);
  const [disabled, setDisabled] = useState(user.disabled);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <form className="rounded border border-[var(--c-800)] p-3 space-y-3" onSubmit={event => {
    event.preventDefault(); if (busy || !isAccountAdmin(getAccountState())) return;
    setBusy(true); setError('');
    void accountsApi.updateUser(user.id, { role, disabled }).then(async () => {
      if (user.id === getAccountState().session?.user?.id) window.dispatchEvent(new Event('r-link-account-refresh'));
      await onSaved();
    }).catch(error => setError(error instanceof Error ? error.message : String(error))).finally(() => setBusy(false));
  }}>
    <div><strong className="text-sm">{user.display_name || user.email || user.id}</strong>{user.email && <p className="text-xs text-[var(--c-400)]">{user.email}</p>}<p className="text-xs text-[var(--c-500)] break-all">账户 ID：{user.id}</p></div>
    <div className="flex flex-wrap gap-3 items-center"><label className="text-xs">权限角色 <select aria-label={`${user.display_name || user.id}的权限角色`} className={control} value={role} disabled={busy} onChange={event => setRole(event.target.value as AccountRole)}>{Object.entries(roleLabels).map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label><label className="flex gap-2 text-xs"><input type="checkbox" checked={disabled} disabled={busy} onChange={event => setDisabled(event.target.checked)} />停用账户</label><button className={control} disabled={busy || (role === user.role && disabled === user.disabled)}>保存权限</button></div>
    {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
  </form>;
}

export function UserAccessSettings() {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => accountsApi.users(signal), []));
  return <section className="space-y-4"><p className="text-sm text-[var(--c-400)]">新成员首次登录后进入等待审批。批准后分配角色，设备和网络资源由所有获准成员共享。密码由统一账户中心管理。</p><button className={control} onClick={() => void refetch()}>刷新用户</button>{loading && <p role="status">正在读取用户…</p>}{error && <p role="alert" className="text-red-400">{error.message}</p>}{data?.map(user => <UserRow key={`${user.id}:${user.role}:${user.disabled}`} user={user} onSaved={refetch} />)}{data?.length === 0 && <p>暂无用户</p>}</section>;
}
