import { useCallback } from 'react';
import { Monitor, Server } from 'lucide-react';
import { devicesApi, type Device } from '../api/devices';
import { usePolling } from '../api/usePolling';
import { useSystemInfo } from '../api/hooks';

export function TopologyView({ onDevices, onSsh }: { onDevices?: () => void; onSsh?: (device: Device) => void }) {
  const { data: devices, error, loading, refetch } = usePolling(useCallback((signal: AbortSignal) => devicesApi.list(signal), []), 5000);
  const { data: server } = useSystemInfo();
  return <section className="space-y-6">
    <div className="flex justify-between gap-4">
      <div><h2 className="text-xl font-bold">设备连接视图</h2><p className="text-sm text-[var(--c-400)] mt-2">显示已登记设备与服务端的 TCP 检测结果；连线不代表物理网络、VPN 或设备间隧道。</p></div>
      <button className="shrink-0 rounded border px-3" onClick={() => void refetch()}>刷新状态</button>
    </div>
    {error && <p role="alert" className="text-red-400">无法读取设备：{error.message}</p>}
    {loading && <p role="status">正在读取设备…</p>}
    {devices && <>
      <div className="mx-auto max-w-sm p-5 rounded-xl border border-[var(--c-700)] bg-[var(--c-900)] text-center">
        <Server className="mx-auto mb-2" /><h3>{server?.hostname || '当前服务端'}</h3>
        <p className="text-xs text-[var(--c-400)]">TCP 检测发起端</p>
      </div>
      {devices.length === 0 ? <div className="rounded-xl border border-[var(--c-800)] p-8 text-center"><p>尚未登记设备</p><p className="text-sm text-[var(--c-400)] mt-2">登记设备后，在设备管理中检测端口，即可在此查看实际结果。</p></div> :
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-x-5">{devices.map(device => <div key={device.id}>
          <div aria-hidden="true" className={`h-10 w-px mx-auto border-l-2 border-dashed ${device.status === 'reachable' ? 'border-emerald-500' : 'border-[var(--c-700)]'}`} />
          <article className="rounded-xl border border-[var(--c-800)] bg-[var(--c-900)] p-5 space-y-2">
            <Monitor size={20} /><h3 className="font-semibold">{device.name}</h3>
            <p className="font-mono text-sm break-all">{device.host.includes(':') ? `[${device.host}]` : device.host}:{device.port}</p>
            <p className={device.status === 'reachable' ? 'text-emerald-400' : 'text-[var(--c-400)]'}>{device.status === 'unchecked' ? '尚未检测' : device.status === 'reachable' ? '上次检测：端口可达' : '上次检测：端口不可达'}</p>
            {device.checked_at && <p className="text-xs text-[var(--c-500)]">{new Date(device.checked_at).toLocaleString()}{device.latency_ms !== null ? ` · ${device.latency_ms} ms` : ''}</p>}
            {onSsh && <button className="text-sm underline" onClick={() => onSsh(device)}>SSH 连接</button>}
          </article>
        </div>)}</div>}
    </>}
    {onDevices && <button className="rounded border px-4 py-2" onClick={onDevices}>管理设备与检测端口</button>}
  </section>;
}
