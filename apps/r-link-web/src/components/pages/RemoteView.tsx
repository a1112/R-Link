import { useEffect, useMemo, useRef, useState } from 'react';
import { devicesApi, type Device, type DeviceInput } from '../../api/devices';
import { probeDevices } from '../../api/device-batch';
import { saveBlob } from '../../utils/download';

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
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [notice, setNotice] = useState('');
  const [batch, setBatch] = useState<{ completed: number; total: number } | null>(null);
  const batchController = useRef<AbortController | null>(null);
  const importInput = useRef<HTMLInputElement>(null);
  const [pendingImport, setPendingImport] = useState<{ name: string; data: unknown; count: number } | null>(null);
  useEffect(() => () => batchController.current?.abort(), []);
  const filtered = useMemo(() => devices.filter(device =>
    (status === 'all' || device.status === status) &&
    `${device.name} ${device.host} ${device.username}`.toLowerCase().includes(search.trim().toLowerCase())), [devices, search, status]);
  useEffect(() => {
    const controller = new AbortController();
    void devicesApi.list(controller.signal).then(setDevices).catch(e => {
      if (!controller.signal.aborted) setError(String(e));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  const perform = async (operation: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return <div className="h-full overflow-auto space-y-5 pb-6">
    <div className="flex flex-wrap justify-between gap-4">
      <div><h2 className="text-xl font-bold">设备管理</h2><p className="text-sm text-[var(--c-400)]">登记设备并从服务端检测指定 TCP 端口。检测结果不代表设备所有服务正常。</p></div>
      <button disabled={busy || loading} onClick={() => void perform(async () => { setDevices(await devicesApi.list()); })} className="rounded border px-3">刷新列表</button>
      <button disabled={busy || loading} onClick={() => { setEditing(undefined); setForm({ ...empty }); }} className="shrink-0 rounded border px-3">添加设备</button>
    </div>
    <div className="flex flex-wrap gap-3 items-center text-sm">
      <input aria-label="搜索设备" placeholder="搜索名称、地址或用户名" className="rounded border border-[var(--c-700)] bg-[var(--c-950)] p-2 flex-1 min-w-48" value={search} disabled={busy} onChange={e => setSearch(e.target.value)} />
      <select aria-label="检测状态筛选" value={status} disabled={busy} onChange={e => setStatus(e.target.value)} className="rounded border border-[var(--c-700)] bg-[var(--c-950)] p-2">
        <option value="all">全部状态</option><option value="reachable">端口可达</option><option value="unreachable">端口不可达</option><option value="unchecked">未检测</option>
      </select>
      <button disabled={busy || loading || !filtered.length} className="rounded border px-3 py-2" onClick={() => void perform(async () => {
        const targets = [...filtered];
        const controller = new AbortController(); batchController.current = controller;
        setBatch({ completed: 0, total: targets.length });
        try {
          const result = await probeDevices(targets, controller.signal,
            checked => setDevices(previous => previous.map(item => item.id === checked.id ? checked : item)),
            completed => setBatch({ completed, total: targets.length }));
          setNotice(`${result.cancelled ? '已停止后续检测' : '批量检测结束'}：完成 ${result.completed}/${targets.length}`);
          if (result.errors.length) setError(result.errors.join('；'));
        } finally { setBatch(null); batchController.current = null; }
      })}>检测筛选结果 ({filtered.length})</button>
      <button disabled={busy || loading} onClick={() => void perform(async () => {
        const inventory = await devicesApi.export();
        saveBlob(new Blob([JSON.stringify(inventory, null, 2)], { type: 'application/json' }), 'r-link-devices.json');
        setNotice('设备清单已导出，不含密码、私钥或旧检测结果。');
      })}>导出清单</button>
      <button disabled={busy || loading} onClick={() => importInput.current?.click()}>导入清单</button>
      <input className="hidden" ref={importInput} type="file" accept=".json,application/json" aria-label="选择设备清单" disabled={busy || loading} onChange={event => {
        const file = event.target.files?.[0]; event.target.value = '';
        if (!file) return;
        void perform(async () => {
          if (file.size > 1024 * 1024) throw new Error('设备清单不能超过 1 MiB');
          const data: unknown = JSON.parse(await file.text());
          if (!data || typeof data !== 'object' || !('devices' in data) || !Array.isArray(data.devices) || data.devices.length > 256) throw new Error('请选择有效的设备清单 JSON，最多 256 台设备');
          setPendingImport({ name: file.name, data, count: data.devices.length });
        });
      }} />
    </div>
    {batch && <div role="status" className="text-sm">正在检测 {batch.completed}/{batch.total}（最多同时 4 台）<button className="ml-4 underline" onClick={() => batchController.current?.abort()}>停止检测</button></div>}
    {notice && <p role="status" className="text-emerald-400 text-sm">{notice}</p>}
    {pendingImport && <div role="dialog" aria-label="导入设备清单" className="rounded border border-[var(--c-700)] p-4 space-y-3">
      <p>{pendingImport.name}：{pendingImport.count} 台设备。重复的主机及端口将跳过；现有设备不会被覆盖。</p>
      <button disabled={busy} className="rounded border px-3 py-2 mr-4" onClick={() => void perform(async () => {
        const result = await devicesApi.import(pendingImport.data);
        setPendingImport(null);
        setNotice(`导入完成：新增 ${result.added} 台，跳过 ${result.skipped} 台。`);
        setDevices(await devicesApi.list());
      })}>确认导入</button>
      <button disabled={busy} onClick={() => setPendingImport(null)}>取消导入</button>
    </div>}
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
    {!loading && devices.length > 0 && filtered.length === 0 && <p>没有符合筛选条件的设备。</p>}
    <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{filtered.map(device => <article key={device.id} className="rounded-xl p-4 border border-[var(--c-800)] bg-[var(--c-900)] space-y-3">
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
