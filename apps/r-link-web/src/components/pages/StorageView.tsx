import { useCallback, useEffect, useRef, useState } from 'react';
import { File, Folder, ArrowUp, Upload, FolderPlus, RefreshCw } from 'lucide-react';
import { storageApi, type StorageEntry } from '../../api/storage';
import { usePolling } from '../../api/usePolling';
import { saveBlob } from '../../utils/download';

const button = 'rounded-lg border border-[var(--c-700)] px-3 py-2 text-sm disabled:opacity-40';
function sizeLabel(size: number | null) {
  if (size === null) return '—';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / 1024 / 1024).toFixed(1)} MiB`;
}
export function StorageView() {
  const [path, setPath] = useState('');
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => storageApi.list(path, signal), [path]));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [actionError, setActionError] = useState('');
  const [form, setForm] = useState<{ kind: 'mkdir' | 'rename'; path: string; name: string } | null>(null);
  const [deleting, setDeleting] = useState<StorageEntry | null>(null);
  const transfer = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => () => transfer.current?.abort(), []);
  const perform = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setActionError(''); setMessage('');
    try { await action(); }
    catch (e) { setActionError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const navigate = (next: string) => { setPath(next); setForm(null); setDeleting(null); setMessage(''); setActionError(''); };
  const disabled = busy || loading;
  return <section className="space-y-5 pb-6">
    <div className="flex flex-wrap justify-between gap-4">
      <div><h2 className="text-xl font-bold">共享文件</h2><p className="mt-2 text-sm text-[var(--c-400)]">文件保存在当前服务端的独立共享区。单文件最多 64 MiB，同名文件不会被覆盖。</p></div>
      <div className="flex gap-2 items-start">
        <button className={button} disabled={disabled} onClick={() => void perform(async () => { await refetch(); })}><RefreshCw size={14} className="inline mr-1" />刷新</button>
        <button className={button} disabled={disabled || !data} onClick={() => setForm({ kind: 'mkdir', path, name: '' })}><FolderPlus size={14} className="inline mr-1" />新建文件夹</button>
        <button className={button} disabled={disabled || !data} onClick={() => fileInput.current?.click()}><Upload size={14} className="inline mr-1" />上传文件</button>
        <input ref={fileInput} type="file" className="hidden" aria-label="选择上传文件" disabled={disabled || !data} onChange={event => {
          const file = event.target.files?.[0]; event.target.value = '';
          if (!file) return;
          if (file.size > (data?.max_file_bytes ?? 64 * 1024 * 1024)) { setActionError('单文件不能超过 64 MiB'); return; }
          void perform(async () => {
            transfer.current = new AbortController();
            await storageApi.upload(path, file, transfer.current.signal);
            setMessage(`已上传 ${file.name}`); await refetch();
          });
        }} />
      </div>
    </div>
    <nav aria-label="文件路径" className="flex flex-wrap gap-2 items-center text-sm">
      <button disabled={disabled || !path} className={button} aria-label="返回上一级" onClick={() => navigate(path.split('/').slice(0, -1).join('/'))}><ArrowUp size={16} /></button>
      <button disabled={disabled} onClick={() => navigate('')}>共享区</button>
      {path.split('/').filter(Boolean).map((part, index, parts) => <span key={index}> / <button disabled={disabled} onClick={() => navigate(parts.slice(0, index + 1).join('/'))}>{part}</button></span>)}
    </nav>
    {busy && <p role="status" className="text-[var(--c-400)]">正在处理，请稍候…</p>}
    {message && <p role="status" className="text-emerald-400">{message}</p>}
    {(actionError || error) && <p role="alert" className="text-red-400">{actionError || error?.message}</p>}
    {form && <form className="rounded-xl border border-[var(--c-700)] p-4 flex gap-3 items-end" onSubmit={event => {
      event.preventDefault();
      void perform(async () => {
        if (form.kind === 'mkdir') await storageApi.mkdir(form.path, form.name);
        else await storageApi.rename(form.path, form.name);
        setForm(null); setMessage(form.kind === 'mkdir' ? '文件夹已创建' : '名称已更新'); await refetch();
      });
    }}>
      <label className="flex-1">{form.kind === 'mkdir' ? '文件夹名称' : '新名称'}<input required maxLength={240} disabled={busy} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="block w-full mt-2 rounded bg-[var(--c-900)] border border-[var(--c-700)] p-2" /></label>
      <button type="submit" className={button} disabled={busy}>保存</button><button type="button" className={button} disabled={busy} onClick={() => setForm(null)}>取消</button>
    </form>}
    {deleting && <div role="dialog" aria-label="确认删除文件" className="rounded-xl border border-red-500/30 p-4 space-y-3">
      <p>删除“{deleting.name}”？此操作无法撤销；仅允许删除文件或空文件夹。</p>
      <button disabled={busy} className={button} onClick={() => void perform(async () => { await storageApi.remove(deleting.path); setDeleting(null); setMessage('已删除'); await refetch(); })}>确认删除</button>
      <button disabled={busy} className={button} onClick={() => setDeleting(null)}>取消删除</button>
    </div>}
    {loading ? <p role="status">正在读取文件…</p> : data && <>
      {data.skipped > 0 && <p className="text-sm text-amber-400">{data.skipped} 个链接或不支持的条目未显示。</p>}
      {data.entries.length === 0 ? <div className="rounded-xl border border-[var(--c-800)] p-10 text-center text-[var(--c-400)]">当前目录为空，可以上传文件或新建文件夹。</div> :
        <div className="overflow-x-auto rounded-xl border border-[var(--c-800)]"><table className="w-full text-sm text-left">
          <thead className="bg-[var(--c-900)] text-[var(--c-400)]"><tr><th className="p-3">名称</th><th className="p-3">大小</th><th className="p-3">修改时间</th><th className="p-3">操作</th></tr></thead>
          <tbody>{data.entries.map(item => <tr key={item.path} className="border-t border-[var(--c-800)]">
            <td className="p-3 max-w-sm break-all">{item.kind === 'directory' ? <button disabled={disabled} onClick={() => navigate(item.path)} className="inline-flex gap-2 items-center text-blue-400"><Folder size={18} />{item.name}</button> : <span className="inline-flex gap-2 items-center"><File size={18} className="shrink-0" />{item.name}</span>}</td>
            <td className="p-3 whitespace-nowrap">{sizeLabel(item.size)}</td><td className="p-3 whitespace-nowrap">{new Date(item.modified_at).toLocaleString()}</td>
            <td className="p-3"><div className="flex gap-3 whitespace-nowrap">
              {item.kind === 'file' && <button disabled={disabled} aria-label={`下载 ${item.name}`} onClick={() => void perform(async () => {
                transfer.current = new AbortController();
                const blob = await storageApi.download(item.path, transfer.current.signal);
                saveBlob(blob, item.name); setMessage('文件已接收，保存由浏览器或系统下载窗口处理。');
              })}>下载</button>}
              <button disabled={disabled} aria-label={`重命名 ${item.name}`} onClick={() => setForm({ kind: 'rename', path: item.path, name: item.name })}>重命名</button>
              <button disabled={disabled} aria-label={`删除 ${item.name}`} onClick={() => setDeleting(item)}>删除</button>
            </div></td>
          </tr>)}</tbody>
        </table></div>}
    </>}
  </section>;
}
export default StorageView;
