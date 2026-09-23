import { useCallback, useState } from 'react';
import { http } from '../../api/client';
import { apiOrigin } from '../../api/authenticated-fetch';
import { usePolling } from '../../api/usePolling';

type ConsoleStatus = { ttyd_running?: boolean; port?: number; console_url?: string };
const loopback = new Set(['127.0.0.1', 'localhost', '[::1]']);
export function localConsoleUrl(raw?: string): string | null {
  if (!raw) return null;
  try {
    const api = new URL(apiOrigin());
    const url = new URL(raw);
    if (!loopback.has(api.hostname) || !loopback.has(url.hostname) || !['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
    return url.href;
  } catch { return null; }
}
export function ConsoleView() {
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => {
    // A completed action invalidates any request begun before it.
    void revision;
    return http.get<ConsoleStatus>('/api/console/status', { signal });
  }, [revision]), 5000);
  const run = async (action: 'start' | 'stop' | 'restart') => {
    setBusy(true); setActionError('');
    try {
      const result = await http.post<{ success?: boolean; error?: string }>(`/api/console/${action}`);
      if (result.success !== true) throw new Error(result.error || '服务端未确认操作成功');
    } catch (e) { setActionError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); setRevision(v => v + 1); }
  };
  const url = data?.ttyd_running ? localConsoleUrl(data.console_url) : null;
  return <section className="space-y-5">
    <div className="flex justify-between flex-wrap gap-4">
      <div><h2 className="text-xl font-bold">Web 控制台</h2><p className="text-sm text-[var(--c-400)] mt-2">通过服务端 ttyd 插件访问本机终端。</p></div>
      <div className="flex gap-3">
        <button disabled={busy || loading} onClick={() => void refetch()}>刷新状态</button>
        {data && <button disabled={busy || loading} onClick={() => void run(data.ttyd_running ? 'stop' : 'start')}>{data.ttyd_running ? '停止控制台' : '启动控制台'}</button>}
        {data?.ttyd_running && <button disabled={busy || loading} onClick={() => void run('restart')}>重启控制台</button>}
      </div>
    </div>
    <p role="status">{busy ? '正在执行操作…' : loading ? '正在读取状态…' : error ? '状态不可用' : data?.ttyd_running ? '控制台运行中' : '控制台已停止'}</p>
    {error && <p role="alert" className="text-red-400">{error.message}</p>}
    {actionError && <p role="alert" className="text-red-400">{actionError}</p>}
    {url ? <iframe key={revision} src={url} title="Web Console" className="w-full h-[60vh] rounded-lg border border-[var(--c-800)] bg-black" sandbox="allow-same-origin allow-scripts allow-forms" /> :
      <div className="p-8 rounded-xl border border-[var(--c-800)] text-[var(--c-400)]">
        {error ? '无法获取服务状态，请检查服务连接后重试。' : data?.ttyd_running ? '此控制台地址无法在当前客户端打开。ttyd 仅监听服务端本机；连接远程设备请使用 SSH 终端。' : loading ? '等待服务端响应。' : '控制台未启动。服务端需已安装 ttyd；启动失败时会显示具体原因。'}
      </div>}
    {data?.ttyd_running && <p className="text-xs text-[var(--c-500)]">服务端报告的监听端口：{data.port ?? '未提供'}</p>}
  </section>;
}
export default ConsoleView;
