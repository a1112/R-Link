import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUp, File, Folder, RefreshCw, Upload } from 'lucide-react';
import { rfileApi, type RFileService } from '../../api/rfile';
import { usePolling } from '../../api/usePolling';
import { saveBlob } from '../../utils/download';

const button = 'rounded-lg border border-[var(--c-700)] px-3 py-2 text-sm disabled:opacity-40';
const panel = 'rounded-xl border border-[var(--c-800)] p-4';
function stateLabel(state: RFileService['state']) {
  return state === 'online' ? '在线' : state === 'unchecked' ? '正在检查' : '不可用';
}
function ServiceCard({ label, service, sessions }: { label: string; service: RFileService; sessions?: number | null }) {
  return <div className={panel}>
    <h3 className="font-semibold">{label} <span className={service.state === 'online' ? 'text-emerald-400' : 'text-amber-400'}>{stateLabel(service.state)}</span></h3>
    <p className="mt-2 break-all text-sm text-[var(--c-400)]">{service.url || '地址配置无效'}</p>
    <p className="mt-1 text-xs text-[var(--c-500)]">最后检查：{service.checked_at ? new Date(service.checked_at).toLocaleString() : '尚未检查'}</p>
    {sessions !== undefined && <p className="mt-2 text-sm text-[var(--c-400)]">活动会话：{sessions !== null && service.state === 'online' ? sessions : '暂不可用'}</p>}
    {service.error && <p className="mt-2 text-sm text-amber-400">{service.error}</p>}
  </div>;
}

function RFileFiles() {
  const [path, setPath] = useState('');
  const listing = usePolling(useCallback((signal: AbortSignal) => rfileApi.list(path, signal), [path]));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const pending = useRef(false);
  const active = useRef(true);
  const transfer = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { active.current = true; return () => { active.current = false; transfer.current?.abort(); }; }, []);
  const perform = async (action: (signal: AbortSignal) => Promise<void>) => {
    if (pending.current) return;
    pending.current = true;
    transfer.current = new AbortController();
    const signal = transfer.current.signal;
    setBusy(true); setError(''); setMessage('');
    try { await action(signal); }
    catch (e) { if (active.current) setError(signal.aborted ? '文件操作已取消' : e instanceof Error ? e.message : '文件操作失败'); }
    finally { pending.current = false; if (active.current) setBusy(false); }
  };
  const navigate = (next: string) => { setPath(next); setMessage(''); setError(''); };
  const disabled = busy || listing.loading;
  return <div className="space-y-4">
    <div className="flex flex-wrap gap-3 items-start justify-between">
      <div><h3 className="text-lg font-semibold">R-File 共享目录</h3><p className="mt-1 text-sm text-[var(--c-400)]">单文件最多 64 MiB，同名文件不会覆盖。访问权限由 R-File 服务决定。</p></div>
      <div className="flex gap-2">
        <button className={button} disabled={disabled} onClick={() => void listing.refetch()}><RefreshCw className="inline mr-1" size={14} />刷新文件</button>
        <button className={button} disabled={disabled || !listing.data?.writable} onClick={() => input.current?.click()}><Upload className="inline mr-1" size={14} />上传文件</button>
        <input ref={input} type="file" className="hidden" aria-label="选择 R-File 上传文件" disabled={disabled || !listing.data?.writable} onChange={event => {
          const file = event.target.files?.[0]; event.target.value = '';
          if (!file) return;
          if (file.size > (listing.data?.max_file_bytes ?? 64 * 1024 * 1024)) { setError('单文件不能超过 64 MiB'); return; }
          void perform(async signal => {
            await rfileApi.upload(path, file, signal);
            if (!active.current) return;
            setMessage(`已上传 ${file.name}`); await listing.refetch();
          });
        }} />
      </div>
    </div>
    <nav aria-label="R-File 文件路径" className="flex gap-2 items-center text-sm flex-wrap">
      <button className={button} aria-label="返回上一级" disabled={disabled || !path} onClick={() => navigate(path.split('/').slice(0, -1).join('/'))}><ArrowUp size={16} /></button>
      <button disabled={disabled} onClick={() => navigate('')}>共享目录</button>
      {path.split('/').filter(Boolean).map((part, index, parts) => <span key={index}> / <button disabled={disabled} onClick={() => navigate(parts.slice(0, index + 1).join('/'))}>{part}</button></span>)}
    </nav>
    {busy && <div className="flex gap-3 items-center"><p role="status">正在传输文件…</p><button className={button} onClick={() => transfer.current?.abort()}>取消传输</button></div>}
    {message && <p role="status" className="text-emerald-400">{message}</p>}
    {(error || listing.error) && <p role="alert" className="text-red-400">{error || listing.error?.message}</p>}
    {listing.loading ? <p role="status">正在读取 R-File 目录…</p> : listing.data && <>
      {!listing.data.writable && <p className="text-sm text-amber-400">当前目录只读。</p>}
      {listing.data.skipped > 0 && <p className="text-sm text-amber-400">{listing.data.skipped} 个链接或不支持的条目未显示。</p>}
      {listing.data.entries.length === 0 ? <p className={panel}>当前目录为空。</p> : <div className="overflow-x-auto rounded-xl border border-[var(--c-800)]"><table className="w-full text-left text-sm">
        <thead className="bg-[var(--c-900)] text-[var(--c-400)]"><tr><th className="p-3">名称</th><th className="p-3">大小</th><th className="p-3">操作</th></tr></thead>
        <tbody>{listing.data.entries.map(item => <tr key={item.path} className="border-t border-[var(--c-800)]">
          <td className="p-3 break-all">{item.kind === 'directory' ? <button className="inline-flex gap-2 items-center text-blue-400" disabled={disabled} onClick={() => navigate(item.path)}><Folder size={18} />{item.name}</button> : <span className="inline-flex gap-2 items-center"><File size={18} />{item.name}</span>}</td>
          <td className="p-3 whitespace-nowrap">{item.size === null ? '—' : item.size < 1024 ? `${item.size} B` : `${(item.size / 1024 / 1024).toFixed(2)} MiB`}</td>
          <td className="p-3">{item.kind === 'file' && <button aria-label={`下载 ${item.name}`} disabled={disabled || (item.size !== null && item.size > listing.data!.max_file_bytes)} onClick={() => void perform(async signal => {
            const blob = await rfileApi.download(item.path, signal);
            if (active.current && !signal.aborted) { saveBlob(blob, item.name); setMessage('文件已接收，保存由浏览器或系统下载窗口处理。'); }
          })}>下载</button>}</td>
        </tr>)}</tbody>
      </table></div>}
    </>}
  </div>;
}

export function RFileView() {
  const service = usePolling(useCallback((signal: AbortSignal) => rfileApi.status(signal), []), 10000);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState('');
  const pending = useRef(false);
  const active = useRef(true);
  const refresh = useRef<AbortController | null>(null);
  useEffect(() => { active.current = true; return () => { active.current = false; refresh.current?.abort(); }; }, []);
  const refreshServices = async () => {
    if (pending.current) return;
    pending.current = true; setRefreshing(true); setRefreshError('');
    refresh.current = new AbortController();
    try { await rfileApi.refresh(refresh.current.signal); if (active.current) await service.refetch(); }
    catch (e) { if (active.current) { setRefreshError(e instanceof Error ? e.message : '服务检查失败'); await service.refetch(); } }
    finally { pending.current = false; if (active.current) setRefreshing(false); }
  };
  const data = service.data;
  return <section aria-label="R-File 服务" className="space-y-5 pb-6">
    <div className="flex gap-4 justify-between items-start"><div><h2 className="text-xl font-bold">R-File</h2><p className="mt-2 text-sm text-[var(--c-400)]">自动使用当前服务端配置的 R-File 文件服务和网络服务。</p></div>
      <button className={button} disabled={refreshing || service.loading} onClick={() => void refreshServices()}><RefreshCw size={14} className="inline mr-1" />刷新服务</button></div>
    {(service.error || refreshError) && <p role="alert" className="text-red-400">{service.error?.message || refreshError}</p>}
    {service.loading && <p role="status">正在读取 R-File 服务状态…</p>}
    {data && <>
      {data.config_error && <p role="alert" className="text-red-400">{data.config_error}</p>}
      <div className="grid gap-4 md:grid-cols-2"><ServiceCard label="文件服务" service={data.watch} /><ServiceCard label="网络服务" service={data.network} sessions={data.network.active_sessions} /></div>
      <div className={panel}><h3 className="font-semibold">R-File 网络设备</h3>
        <p className="mt-2 text-sm text-[var(--c-400)]">设备状态来自 R-File 网络服务。文件访问仍取决于设备的共享设置和访问权限。</p>
        {data.devices.length === 0 ? <p className="mt-3 text-sm text-[var(--c-400)]">{data.network.state === 'online' ? '当前没有可见的 R-File 设备。' : '网络服务恢复后可读取设备。'}</p> : <ul className="mt-3 space-y-3">{data.devices.map(device => <li key={device.deviceId} className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--c-800)] pt-3">
          <div><p>{device.deviceName || device.deviceId}</p><p className="text-xs text-[var(--c-500)] break-all">{device.deviceId} · {device.platform || '未知系统'}</p></div>
          <p className="text-sm text-[var(--c-400)]">{device.presence === 'online' ? '在线' : device.presence === 'offline' ? '离线' : device.presence || '状态未知'} · {device.connectivity || '连接状态未知'}</p>
        </li>)}</ul>}
      </div>
      {!data.files.enabled ? <p className={panel}>{data.files.reason}</p> : data.watch.state === 'online' ? <RFileFiles /> : <p className={panel}>文件服务恢复后可读取已配置的共享目录。</p>}
    </>}
  </section>;
}
export default RFileView;
