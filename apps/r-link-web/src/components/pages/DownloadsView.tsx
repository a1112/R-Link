import { useCallback, useState } from 'react';
import { servicesApi, type Download } from '../../api/services';
import { usePolling } from '../../api/usePolling';
import { saveBlob } from '../../utils/download';
import { ServiceField, ServiceMessage, serviceButton as button, useServiceAction } from '../common/ServiceControls';

const states: Record<Download['state'], string> = { queued: '排队中', running: '下载中', paused: '已暂停', failed: '失败', completed: '已完成', cancelled: '已取消' };
const bytes = (value: number) => `${(value / 1024 / 1024).toFixed(2)} MiB`;
export function DownloadsView() {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => servicesApi.downloads(signal), []), 1500);
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [deleting, setDeleting] = useState<Download | null>(null);
  const action = useServiceAction();
  return <section className="space-y-5 pb-6">
    <h2 className="text-xl font-bold">下载管理</h2>
    <p className="text-sm text-[var(--c-400)]">文件下载到当前服务端，关闭客户端后继续。支持 HTTP/HTTPS、暂停及安全续传；下载完成后可另存到本机。</p>
    <form className="grid gap-3 md:grid-cols-[2fr_1fr_auto] items-end" onSubmit={e => { e.preventDefault(); void action.run(async () => { await servicesApi.createDownload(url, name); setUrl(''); setName(''); await refetch(); }); }}>
      <ServiceField label="下载地址" required type="url" maxLength={4096} value={url} disabled={action.busy} onChange={e => setUrl(e.target.value)} placeholder="https://example.com/file.zip" />
      <ServiceField label="保存名称" required maxLength={160} value={name} disabled={action.busy} onChange={e => setName(e.target.value)} placeholder="file.zip" />
      <button className={button} disabled={action.busy}>添加下载</button>
    </form>
    <ServiceMessage error={action.error || error?.message} />
    {loading && <p role="status">正在加载任务…</p>}
    {data?.length === 0 && <p className="text-[var(--c-400)]">暂无下载任务。</p>}
    {data?.map(item => <article key={item.id} className="rounded-xl border border-[var(--c-800)] p-4 space-y-3">
      <div className="flex justify-between gap-3"><strong className="break-all">{item.name}</strong><span>{states[item.state]}</span></div>
      <p className="text-sm">{bytes(item.downloaded)} / {item.total === null ? '未知大小' : bytes(item.total)}</p>
      {item.total !== null && item.total > 0 && <progress className="w-full" aria-label={`${item.name} 下载进度`} value={item.downloaded} max={item.total} />}
      {item.error && <p className="text-sm text-red-400">{item.error}</p>}
      <div className="flex gap-2 flex-wrap">
        {(['running', 'queued'].includes(item.state)) && <button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await servicesApi.downloadAction(item.id, 'pause'); await refetch(); })}>暂停</button>}
        {(['paused', 'failed', 'cancelled'].includes(item.state)) && <button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await servicesApi.downloadAction(item.id, 'resume'); await refetch(); })}>继续</button>}
        {!['completed', 'cancelled'].includes(item.state) && <button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await servicesApi.downloadAction(item.id, 'cancel'); await refetch(); })}>取消任务</button>}
        {item.state === 'completed' && <button className={button} disabled={action.busy} onClick={() => void action.run(async () => saveBlob(await servicesApi.downloadFile(item.id), item.name))}>保存到本机</button>}
        <button className={button} disabled={action.busy} onClick={() => setDeleting(item)}>删除</button>
      </div>
    </article>)}
    {deleting && <div role="dialog" aria-label="删除下载任务" className="rounded-xl border border-red-500/30 p-4 space-y-3"><p>删除“{deleting.name}”及服务端已下载文件？</p><button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await servicesApi.deleteDownload(deleting.id); setDeleting(null); await refetch(); })}>确认删除</button> <button className={button} disabled={action.busy} onClick={() => setDeleting(null)}>保留</button></div>}
  </section>;
}
export default DownloadsView;
