import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { pluginsApi } from '../api/plugins';

interface DetailPlugin {
  name: string; description: string; version: string; author: string;
}
export function PluginDetailModal({ plugin, onClose, onUninstall }: {
  plugin: DetailPlugin; onClose: () => void; onUninstall?: (plugin: DetailPlugin) => Promise<void>;
}) {
  const [tab, setTab] = useState<'overview' | 'config' | 'logs'>('overview');
  const [config, setConfig] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setError(''); setMessage(''); setConfig(''); setLogs([]);
    if (tab === 'overview') { setLoading(false); return; }
    setLoading(true);
    const read = async () => {
      try {
        if (tab === 'config') {
          const value = await pluginsApi.getConfig(plugin.name);
          if (active) setConfig(JSON.stringify(value, null, 2));
        } else {
          const value = await pluginsApi.getLogs(plugin.name, 100);
          if (active) setLogs(Array.isArray(value.logs) ? value.logs : value.logs ? value.logs.split('\n') : []);
        }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : String(e)); }
      finally { if (active) setLoading(false); }
    };
    void read();
    return () => { active = false; };
  }, [plugin.name, tab, revision]);
  return <div className="fixed inset-0 z-50 flex items-center justify-center p-8 bg-black/60" onClick={() => { if (!busy) onClose(); }}>
    <section role="dialog" aria-modal="true" aria-label={plugin.name} className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl border border-[var(--c-700)] bg-[var(--c-950)] p-6 space-y-5" onClick={e => e.stopPropagation()}>
      <div className="flex justify-between"><h2 className="text-xl font-bold">{plugin.name}</h2><button disabled={busy} aria-label="关闭插件详情" onClick={onClose}><X /></button></div>
      <div className="flex gap-4 border-b border-[var(--c-800)] pb-3">{(['overview', 'config', 'logs'] as const).map(id => <button key={id} disabled={busy} aria-pressed={tab === id} className={tab === id ? 'text-[var(--c-100)] underline' : 'text-[var(--c-500)]'} onClick={() => setTab(id)}>{{ overview: '概览', config: '配置', logs: '运行日志' }[id]}</button>)}</div>
      {error && <p role="alert" className="text-red-400">{error}</p>}
      {message && <p role="status" className="text-emerald-400">{message}</p>}
      {tab === 'overview' ? <div className="space-y-4"><p>{plugin.description || '插件未提供描述'}</p><p className="text-sm text-[var(--c-400)]">版本：{plugin.version || '未提供'} · 作者：{plugin.author || '未提供'}</p>
        {onUninstall && <button disabled={busy} className="border rounded px-3 py-2 text-red-400" onClick={async () => {
          if (!window.confirm(`确认卸载插件 ${plugin.name}？`)) return;
          setBusy(true);
          try { await onUninstall(plugin); } finally { setBusy(false); }
        }}>卸载插件</button>}</div> :
        loading ? <p role="status">正在读取…</p> : <>
          <button disabled={busy} className="text-sm underline" onClick={() => setRevision(v => v + 1)}>重新读取</button>
          {tab === 'logs' ? <pre className="text-xs whitespace-pre-wrap break-all rounded bg-black/30 p-4 max-h-80 overflow-auto">{error ? '日志不可用' : logs.length ? logs.join('\n') : '暂无运行日志'}</pre> :
            <form className="space-y-3" onSubmit={async e => {
              e.preventDefault(); setError(''); setMessage(''); setBusy(true);
              try {
                const value: unknown = JSON.parse(config);
                if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('配置必须是 JSON 对象');
                await pluginsApi.setConfig(plugin.name, value as Record<string, unknown>);
                setMessage('配置已保存；如插件需要重新加载，请在插件中心重启。');
              } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
              finally { setBusy(false); }
            }}>
              <label className="block">插件配置（JSON）<textarea aria-label="插件配置（JSON）" className="block w-full h-56 font-mono text-xs bg-black/30 p-3 rounded mt-2" disabled={busy || !config} value={config} onChange={e => setConfig(e.target.value)} /></label>
              <button disabled={busy || !config} className="rounded border px-3 py-2">{busy ? '正在保存…' : '保存配置'}</button>
            </form>}
        </>}
    </section>
  </div>;
}
