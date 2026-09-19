import { useEffect, useState } from 'react';
import { devicesApi, type Device, type DeviceInput } from '../../api/devices';

const empty: DeviceInput = { name: '', host: '', port: 22, username: '' };
const inputStyle = 'w-full rounded border border-[var(--c-700)] bg-[var(--c-950)] p-2';
export function RemoteView({ onSsh }: { onSsh?: (device: Device) => void }) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState<DeviceInput | null>(null);
  const [editing, setEditing] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<string>();
  useEffect(() => {
    const controller = new AbortController();
    void devicesApi.list(controller.signal).then(setDevices).catch(e => {
      if (!controller.signal.aborted) setError(String(e));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  const perform = async (operation: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return <div className="h-full overflow-auto space-y-5 pb-6">
    <div className="flex justify-between gap-4">
      <div><h2 className="text-xl font-bold">设备管理</h2><p className="text-sm text-[var(--c-400)]">登记设备并从服务端检测指定 TCP 端口。检测结果不代表设备所有服务正常。</p></div>
      <button disabled={busy || loading} onClick={() => void perform(async () => { setDevices(await devicesApi.list()); })} className="rounded border px-3">刷新列表</button>
      <button disabled={busy || loading} onClick={() => { setEditing(undefined); setForm({ ...empty }); }} className="shrink-0 rounded border px-3">添加设备</button>
    </div>
    {error && <p role="alert" className="text-red-400">{error}</p>}
    {loading && <p>正在读取设备…</p>}
    {!loading && devices.length === 0 && !error && <p className="text-[var(--c-400)]">尚未登记设备。添加主机名或 IP 地址后可检测连通性。</p>}
    {form && <form className="p-4 rounded-xl border border-[var(--c-700)] space-y-3" onSubmit={event => {
      event.preventDefault();
      void perform(async () => {
        const saved = await devicesApi.save(form, editing);
        setDevices(previous => [...previous.filter(item => item.id !== saved.id), saved]);
        setForm(null);
      });
    }}>
      <h3>{editing ? '编辑设备' : '添加设备'}</h3>
      <div className="grid md:grid-cols-2 gap-3">
        <label>设备名称<input className={inputStyle} required maxLength={80} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
        <label>主机名或 IP<input className={inputStyle} required maxLength={253} value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} /></label>
        <label>TCP / SSH 端口<input className={inputStyle} required type="number" min={1} max={65535} value={form.port} onChange={e => setForm({ ...form, port: Number(e.target.value) })} /></label>
        <label>SSH 用户名（可选）<input className={inputStyle} maxLength={80} value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></label>
      </div>
      <p className="text-xs text-[var(--c-500)]">仅保存设备地址和用户名；连接时再提供密码或私钥。</p>
      <button disabled={busy} type="submit" className="rounded border px-3 py-2 mr-3">保存设备</button>
      <button disabled={busy} type="button" onClick={() => setForm(null)}>取消</button>
    </form>}
    <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{devices.map(device => <article key={device.id} className="rounded-xl p-4 border border-[var(--c-800)] bg-[var(--c-900)] space-y-3">
      <h3 className="font-semibold">{device.name}</h3>
      <p className="font-mono text-sm break-all">{device.host.includes(':') ? `[${device.host}]` : device.host}:{device.port}</p>
      <p className={device.status === 'reachable' ? 'text-emerald-400' : 'text-[var(--c-400)]'}>{device.status === 'unchecked' ? '尚未检测' : device.status === 'reachable' ? `上次检测：端口可达 · ${device.latency_ms} ms` : '上次检测：端口不可达'}</p>
      {device.checked_at && <p className="text-xs text-[var(--c-500)]">检测时间：{new Date(device.checked_at).toLocaleString()}</p>}
      <div className="flex flex-wrap gap-3 text-sm">
        <button disabled={busy} onClick={() => void perform(async () => {
          const checked = await devicesApi.probe(device.id);
          setDevices(previous => previous.map(item => item.id === checked.id ? checked : item));
        })}>检测端口</button>
        <button disabled={busy || !onSsh} onClick={() => onSsh?.(device)}>SSH 连接</button>
        <button disabled={busy} onClick={() => { setEditing(device.id); setForm({ name: device.name, host: device.host, port: device.port, username: device.username }); }}>编辑</button>
        <button disabled={busy} onClick={() => setDeleting(device.id)}>删除</button>
      </div>
      {deleting === device.id && <div className="text-sm space-x-3"><span>确认删除此设备？</span><button disabled={busy} onClick={() => void perform(async () => {
        await devicesApi.remove(device.id); setDevices(previous => previous.filter(item => item.id !== device.id)); setDeleting(undefined);
      })}>确认删除</button><button onClick={() => setDeleting(undefined)}>取消</button></div>}
    </article>)}</div>
  </div>;
}
export default RemoteView;
