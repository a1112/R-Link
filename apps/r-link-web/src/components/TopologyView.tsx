import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, Plus, RefreshCw, Network, Folder } from 'lucide-react';
import { devicesApi, type Device } from '../api/devices';
import { rfileApi } from '../api/rfile';
import { systemApi } from '../api/system';
import { meshApi } from '../api/mesh';
import { fabricApi } from '../api/fabric';
import { clientDeviceFallback, getClientDeviceInfo } from '../api/client-device';
import { usePolling } from '../api/usePolling';
import { deviceTypes } from './device-presentation';
import { filterNodes, layoutNodes, makeNodes, presenceLabels, type Filters } from './topology/model';
import { TopologyDetails } from './topology/TopologyDetails';
import { TopologyCanvas } from './topology/TopologyCanvas';
import { useTopologyDocument } from './topology/useTopologyDocument';
import { apiOrigin } from '../api/service-access';
import { topologyAccountScope } from '../api/account-access';
import './topology/topology.css';

export function TopologyView({ onDevices, onManage, onSsh, onRFile, onStorage }: {
  onDevices?: () => void; onManage?: (device?: Device) => void; onSsh?: (device: Device) => void; onRFile?: () => void; onStorage?: () => void;
}) {
  const inventory = usePolling(useCallback((signal: AbortSignal) => devicesApi.list(signal), []), 5000);
  const rfile = usePolling(useCallback((signal: AbortSignal) => rfileApi.status(signal), []), 10000);
  const server = usePolling(useCallback((signal: AbortSignal) => systemApi.getInfo(signal), []), 10000);
  const client = usePolling(useCallback(() => getClientDeviceInfo(), []), 10000);
  const mesh = usePolling(useCallback(async (signal: AbortSignal) => {
    const status = await meshApi.status(signal);
    return { status, peers: status.configured && status.reachable ? await meshApi.peers(signal) : [] };
  }, []), 10000);
  const fabric = usePolling(useCallback(async (signal: AbortSignal) => {
    const status = await fabricApi.status(signal);
    return { status, peers: status.configured ? await fabricApi.peers(signal) : [] };
  }, []), 10000);
  const [filters, setFilters] = useState<Filters>({ query: '', status: 'all', type: 'all', source: 'all' });
  const [selection, setSelection] = useState<string[]>([]);
  const [focusDetails, setFocusDetails] = useState(true);
  const [editRequest, setEditRequest] = useState<{ id: string; token: number } | null>(null);
  const selectNodes = (ids: string[], focus = true) => { setFocusDetails(focus); setSelection(ids); };
  const store = useTopologyDocument(topologyAccountScope(apiOrigin()));
  const [refreshing, setRefreshing] = useState(false);
  const refreshPending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const nodes = useMemo(() => makeNodes(inventory.data ?? [], rfile.data, client.data ?? clientDeviceFallback(), mesh.data, fabric.data).map(node => ({ ...node, name: store.document.annotations[node.id]?.name || node.name })), [inventory.data, rfile.data, client.data, mesh.data, fabric.data, store.document.annotations]);
  const visible = useMemo(() => filterNodes(nodes, filters), [nodes, filters]);
  const layout = useMemo(() => layoutNodes(nodes), [nodes]);
  const selected = selection.length === 1 ? visible.find(node => node.id === selection[0]) : undefined;
  useEffect(() => {
    const remaining = selection.filter(id => visible.some(node => node.id === id));
    if (remaining.length !== selection.length) setSelection(remaining);
  }, [selection, visible]);
  const nodeButtons = useRef(new Map<string, HTMLButtonElement>());
  const changeFilter = (value: Partial<Filters>) => setFilters(previous => ({ ...previous, ...value }));
  const close = () => { if (selected) nodeButtons.current.get(selected.id)?.focus({ preventScroll: true }); setSelection([]); };
  const refresh = async () => {
    if (refreshPending.current) return;
    refreshPending.current = true; setRefreshing(true);
    try { await Promise.all([inventory.refetch(), rfile.refetch(), server.refetch(), client.refetch(), mesh.refetch(), fabric.refetch()]); }
    finally { refreshPending.current = false; if (mounted.current) setRefreshing(false); }
  };
  const counts = { all: nodes.length, online: nodes.filter(node => node.status === 'online').length, offline: nodes.filter(node => node.status === 'offline').length, unknown: nodes.filter(node => node.status === 'unknown').length };
  const loading = inventory.loading || rfile.loading;
  const manage = onManage ?? onDevices;
  return <section className={`topology-home${selected ? ' has-details' : ''}`} aria-label="设备拓扑">
    <div className="topology-main">
      <div className="topology-heading"><div><h1>我的设备</h1><p>设备拓扑 <span>·</span> 自动更新</p></div>
        <div className="topology-heading-actions"><label className="topology-search"><Search size={17} /><input aria-label="搜索设备" placeholder="搜索设备、地址或标签…" value={filters.query} onChange={event => changeFilter({ query: event.target.value })} /></label>
          <button className="topology-button icon-button" aria-label="刷新状态" title="刷新状态" disabled={refreshing} onClick={() => void refresh()}><RefreshCw size={17} className={refreshing ? 'animate-spin' : ''} /></button>
          {manage && <button className="topology-button primary" onClick={() => manage()}><Plus size={18} />添加设备</button>}
        </div>
      </div>
      <div className="topology-toolbar"><div className="topology-counts">{(['all', 'online', 'offline', 'unknown'] as const).map(status => {
        const label = status === 'all' ? '全部' : presenceLabels[status];
        return <button key={status} aria-label={`${label}设备 ${counts[status]}`} aria-pressed={filters.status === status} className={filters.status === status ? 'active' : ''} onClick={() => changeFilter({ status })}>
          {status !== 'all' && <i className={`topology-dot is-${status}`} aria-hidden="true" />}{label}<strong>{counts[status]}</strong></button>;
      })}</div><div className="topology-selects">
        <select aria-label="设备类型" value={filters.type} onChange={event => changeFilter({ type: event.target.value })}><option value="all">全部设备类型</option>{Object.entries(deviceTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <select aria-label="设备来源" value={filters.source} onChange={event => changeFilter({ source: event.target.value })}><option value="all">全部来源</option><option value="client">本电脑</option><option value="inventory">登记设备</option><option value="rfile">R-File</option></select>
      </div></div>
      {(inventory.error || rfile.error || server.error) && <div role="alert" className="topology-alert">
        {inventory.error && <p>设备清单暂不可用：{inventory.error.message}</p>}{rfile.error && <p>R-File 状态暂不可用：{rfile.error.message}</p>}{server.error && <p>服务端信息暂不可用：{server.error.message}</p>}
      </div>}
      {rfile.data && rfile.data.network.state !== 'online' && <p className="topology-muted">R-File 网络服务{rfile.data.network.state === 'unchecked' ? '正在检查' : '暂不可用'}，设备状态待确认。</p>}
      {loading && nodes.length > 0 && <p className="topology-muted" role="status">正在读取{[inventory.loading && '设备清单', rfile.loading && 'R-File'].filter(Boolean).join('、')}…</p>}
      {!loading && !inventory.error && !rfile.error && nodes.every(node => node.source === 'client') && <p className="topology-muted">尚未发现其他设备。添加设备，或完成设备入网。</p>}
      <TopologyCanvas layout={layout} visibleIds={visible.map(node => node.id)} selection={selection} onSelection={selectNodes} store={store} editRequest={editRequest}
        serverName={server.data?.hostname || '当前服务端'} serverStatus={server.error ? '连接待确认' : server.loading ? '正在读取…' : undefined}
        onEditDevice={onManage} nodeButtons={nodeButtons}>
        {loading && !nodes.length && <div className="topology-empty" role="status"><RefreshCw size={24} className="animate-spin" /><h3>正在读取设备…</h3></div>}
        {!loading && !visible.length && <div className="topology-empty"><Network size={32} strokeWidth={1.3} /><h3>{nodes.length ? '没有符合筛选条件的设备' : inventory.error || rfile.error ? '设备信息暂不可用' : '尚未发现设备'}</h3><p>{nodes.length ? '调整搜索或筛选条件以查看其他设备。' : '添加设备，或连接已有的 R-File 网络服务。'}</p>{nodes.length ? <button className="topology-button" onClick={() => changeFilter({ query: '', status: 'all', type: 'all', source: 'all' })}>清除筛选</button> : onRFile && <button className="topology-button" onClick={onRFile}>查看 R-File 服务</button>}</div>}
      </TopologyCanvas>
      <div className="topology-footnote"><span>本电脑为当前操作端；连线表示管理、登记或发现关系，不代表组网直连。服务端不计入设备数。</span>{onStorage && <button onClick={onStorage}><Folder size={14} />服务端共享文件</button>}</div>
    </div>
    {selected && <TopologyDetails node={selected} annotation={store.document.annotations[selected.id]} focusOnOpen={focusDetails} onAnnotate={() => setEditRequest(previous => ({ id: selected.id, token: (previous?.token ?? 0) + 1 }))} onClose={close} onSsh={onSsh} onManage={onManage} onRFile={onRFile} />}
  </section>;
}
