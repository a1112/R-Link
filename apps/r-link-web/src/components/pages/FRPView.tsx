import { useCallback, useState } from 'react';
import { servicesApi, type Tunnel, type TunnelInput } from '../../api/services';
import { usePolling } from '../../api/usePolling';
import { ServiceField, ServiceMessage, ServiceLogs, serviceButton as button, serviceInput, useServiceAction } from '../common/ServiceControls';

const empty: TunnelInput = { name: '', server_host: '', server_port: 7000, local_host: '127.0.0.1', local_port: 22, remote_port: 6000, protocol: 'tcp', token_env: 'R_LINK_FRP_TOKEN', autostart: false };
export function FRPView() {
  const { data, loading, error, refetch } = usePolling(useCallback(async (signal: AbortSignal) => ({ tunnels: await servicesApi.tunnels(signal), capabilities: await servicesApi.capabilities(signal) }), []), 3000);
  const [form, setForm] = useState<TunnelInput | null>(null);
  const [editing, setEditing] = useState<string>();
  const [deleting, setDeleting] = useState<Tunnel | null>(null);
  const [logs, setLogs] = useState<string | null>(null);
  const action = useServiceAction();
  return <section className="space-y-5 pb-6">
    <div className="flex justify-between"><h2 className="text-xl font-bold">FRP 隧道</h2><button className={button} disabled={action.busy} onClick={() => { setEditing(undefined); setForm({ ...empty }); }}>新建隧道</button></div>
    <p className="text-sm text-[var(--c-400)]">将服务端可访问的 TCP/UDP 服务映射到你的 frps 服务器。进程运行状态不等于隧道连通，请结合日志验证。</p>
    {data && !data.capabilities.frp.available && <p className="text-amber-400">{data.capabilities.frp.reason}</p>}
    <ServiceMessage error={action.error || error?.message} />
    {form && <form className="rounded-xl border border-[var(--c-700)] p-4 space-y-4" onSubmit={e => { e.preventDefault(); void action.run(async () => { await servicesApi.saveTunnel(form, editing); setForm(null); await refetch(); }); }}>
      <fieldset disabled={action.busy} className="grid gap-3 md:grid-cols-2">
        <ServiceField label="隧道名称" required pattern="[a-zA-Z0-9_-]+" maxLength={80} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
        <label>协议<select className={serviceInput} value={form.protocol} onChange={e => setForm({ ...form, protocol: e.target.value as 'tcp' | 'udp' })}><option value="tcp">TCP</option><option value="udp">UDP</option></select></label>
        <ServiceField label="frps 服务器地址" required value={form.server_host} onChange={e => setForm({ ...form, server_host: e.target.value })} />
        <ServiceField label="frps 控制端口" required type="number" min={1} max={65535} value={form.server_port} onChange={e => setForm({ ...form, server_port: Number(e.target.value) })} />
        <ServiceField label="本地目标地址（从服务端访问）" required value={form.local_host} onChange={e => setForm({ ...form, local_host: e.target.value })} />
        <ServiceField label="本地目标端口" required type="number" min={1} max={65535} value={form.local_port} onChange={e => setForm({ ...form, local_port: Number(e.target.value) })} />
        <ServiceField label="公网映射端口" required type="number" min={1} max={65535} value={form.remote_port} onChange={e => setForm({ ...form, remote_port: Number(e.target.value) })} />
        <ServiceField label="令牌环境变量名称" required pattern="R_LINK_FRP_TOKEN(_[A-Z0-9_]+)?" value={form.token_env} onChange={e => setForm({ ...form, token_env: e.target.value })} />
      </fieldset>
      <p className="text-xs text-[var(--c-400)]">在服务端设置上述环境变量为 frps 令牌。此处填写变量名，密钥不会返回客户端。</p>
      <label className="block text-sm"><input type="checkbox" disabled={action.busy} checked={form.autostart} onChange={e => setForm({ ...form, autostart: e.target.checked })} /> 服务端重启后自动启动</label>
      <button className={button} disabled={action.busy}>保存</button> <button type="button" className={button} disabled={action.busy} onClick={() => setForm(null)}>取消</button>
    </form>}
    {loading && <p role="status">正在读取隧道…</p>}
    {data?.tunnels.length === 0 && <p className="text-[var(--c-400)]">暂无隧道，创建配置后点击启动。</p>}
    {data?.tunnels.map(item => <article key={item.id} className="rounded-xl border border-[var(--c-800)] p-4 space-y-3">
      <div className="flex justify-between gap-3"><strong>{item.name}</strong><span>{item.runtime.state === 'running' ? '进程运行中' : item.runtime.state === 'error' ? '进程异常' : '已停止'}</span></div>
      <p className="text-sm break-all">{item.protocol.toUpperCase()} · {item.local_host}:{item.local_port} → {item.server_host}:{item.remote_port}</p>
      {item.runtime.error && <p className="text-red-400 text-sm">{item.runtime.error}</p>}
      <div className="flex flex-wrap gap-2">
        <button className={button} disabled={action.busy || (item.runtime.state !== 'running' && !data.capabilities.frp.available)} onClick={() => void action.run(async () => { await servicesApi.tunnelAction(item.id, item.runtime.state === 'running' ? 'stop' : 'start'); await refetch(); })}>{item.runtime.state === 'running' ? '停止' : '启动'}</button>
        <button className={button} disabled={action.busy || item.runtime.state === 'running'} onClick={() => { setEditing(item.id); setForm({ name: item.name, server_host: item.server_host, server_port: item.server_port, local_host: item.local_host, local_port: item.local_port, remote_port: item.remote_port, protocol: item.protocol, token_env: item.token_env, autostart: item.autostart }); }}>编辑</button>
        <button className={button} disabled={action.busy} onClick={() => void action.run(async () => setLogs((await servicesApi.tunnelLogs(item.id)).logs))}>日志</button>
        <button className={button} disabled={action.busy} onClick={() => setDeleting(item)}>删除</button>
      </div>
    </article>)}
    {deleting && <div role="dialog" aria-label="删除隧道" className="rounded-xl border border-red-500/30 p-4"><p>停止并删除“{deleting.name}”？</p><button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await servicesApi.deleteTunnel(deleting.id); setDeleting(null); await refetch(); })}>确认删除</button> <button className={button} disabled={action.busy} onClick={() => setDeleting(null)}>保留</button></div>}
    <ServiceLogs value={logs} close={() => setLogs(null)} />
  </section>;
}
export default FRPView;
