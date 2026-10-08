import { useCallback } from 'react';
import { devicesApi } from '../../api/devices';
import { meshApi } from '../../api/mesh';
import { usePolling } from '../../api/usePolling';

/** Viewers only request endpoints in the server's read-only allowlist. */
export function ReadOnlyInventory({ mesh = false }: { mesh?: boolean }) {
  const { data, error, loading, refetch } = usePolling(useCallback(async (signal: AbortSignal) => {
    if (!mesh) return { devices: await devicesApi.list(signal), status: null, peers: [] };
    const status = await meshApi.status(signal);
    return { devices: [], status, peers: status.configured ? await meshApi.peers(signal) : [] };
  }, [mesh]), 15000);
  return <section className="space-y-5"><div className="flex justify-between items-start"><div><h2 className="text-xl font-semibold">{mesh ? '虚拟组网状态' : '共享设备'}</h2><p className="text-sm text-[var(--c-400)]">当前角色为只读成员；请联系管理员申请操作权限。</p></div><button className="rounded border px-3 py-2" onClick={() => void refetch()}>刷新</button></div>
    {loading && <p role="status">正在读取…</p>}{error && <p role="alert" className="text-red-400">{error.message}</p>}
    {data?.status && <p role="status">{data.status.configured ? `${data.status.connected}/${data.status.peers} 节点连接管理端` : data.status.reason || '尚未配置组网'}</p>}
    {data?.devices.map(device => <article key={device.id} className="rounded-xl border border-[var(--c-800)] p-4"><strong>{device.name}</strong><p className="text-sm">{device.host}:{device.port} · {device.platform || '未知系统'}</p><p className="text-xs text-[var(--c-400)]">组网：{device.connection_status || '未确认'} · TCP：{device.status === 'reachable' ? '可达' : device.status === 'unreachable' ? '不可达' : '未检测'}</p></article>)}
    {data?.peers.map(peer => <article key={peer.id} className="rounded-xl border border-[var(--c-800)] p-4"><strong>{peer.name}</strong><p className="text-sm">{peer.ip || '尚未分配虚拟地址'} · {peer.connected ? '管理端在线' : '离线'}</p></article>)}
    {data && !error && (mesh ? data.peers.length === 0 && data.status?.configured : data.devices.length === 0) && <p>暂无设备</p>}
  </section>;
}
