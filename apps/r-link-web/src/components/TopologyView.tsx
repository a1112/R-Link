import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, Plus, Minus, Maximize, RefreshCw, Server, Network, Folder } from 'lucide-react';
import { devicesApi, type Device } from '../api/devices';
import { rfileApi } from '../api/rfile';
import { systemApi } from '../api/system';
import { usePolling } from '../api/usePolling';
import { deviceTypes } from './device-presentation';
import { filterNodes, layoutNodes, makeNodes, presenceLabels, type Filters, type Presence } from './topology/model';
import { deviceIcons, StatusBadge, TopologyDetails } from './topology/TopologyDetails';
import './topology/topology.css';

export function TopologyView({ onDevices, onManage, onSsh, onRFile, onStorage }: {
  onDevices?: () => void; onManage?: (device?: Device) => void; onSsh?: (device: Device) => void; onRFile?: () => void; onStorage?: () => void;
}) {
  const inventory = usePolling(useCallback((signal: AbortSignal) => devicesApi.list(signal), []), 5000);
  const rfile = usePolling(useCallback((signal: AbortSignal) => rfileApi.status(signal), []), 10000);
  const server = usePolling(useCallback((signal: AbortSignal) => systemApi.getInfo(signal), []), 10000);
  const [filters, setFilters] = useState<Filters>({ query: '', status: 'all', type: 'all', source: 'all' });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const refreshPending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const nodes = useMemo(() => makeNodes(inventory.data ?? [], rfile.data), [inventory.data, rfile.data]);
  const visible = useMemo(() => filterNodes(nodes, filters), [nodes, filters]);
  const layout = useMemo(() => layoutNodes(visible), [visible]);
  const selected = visible.find(node => node.id === selectedId);
  useEffect(() => { if (selectedId && !selected) setSelectedId(null); }, [selectedId, selected]);
  const viewport = useRef<HTMLDivElement>(null);
  const nodeButtons = useRef(new Map<string, HTMLButtonElement>());
  const [size, setSize] = useState({ width: 960, height: 640 });
  useEffect(() => {
    const element = viewport.current;
    if (!element || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => setSize({ width: element.clientWidth, height: element.clientHeight }));
    observer.observe(element); return () => observer.disconnect();
  }, []);
  const [manualZoom, setManualZoom] = useState<number | null>(null);
  const fit = Math.max(size.width < 480 ? 0.6 : 0.35, Math.min(1, (size.width - 32) / layout.width, (size.height - 32) / layout.height));
  const zoom = manualZoom ?? fit;
  const drag = useRef<{ id: number; x: number; y: number; left: number; top: number } | null>(null);
  const changeFilter = (value: Partial<Filters>) => { setFilters(previous => ({ ...previous, ...value })); setManualZoom(null); if (viewport.current) { viewport.current.scrollTop = 0; viewport.current.scrollLeft = 0; } };
  const close = () => { if (selectedId) nodeButtons.current.get(selectedId)?.focus({ preventScroll: true }); setSelectedId(null); };
  const refresh = async () => {
    if (refreshPending.current) return;
    refreshPending.current = true; setRefreshing(true);
    try { await Promise.all([inventory.refetch(), rfile.refetch(), server.refetch()]); }
    finally { refreshPending.current = false; if (mounted.current) setRefreshing(false); }
  };
  const resetView = () => { setManualZoom(null); if (viewport.current) { viewport.current.scrollTop = 0; viewport.current.scrollLeft = 0; } };
  const counts = { all: nodes.length, online: nodes.filter(node => node.status === 'online').length, offline: nodes.filter(node => node.status === 'offline').length, unknown: nodes.filter(node => node.status === 'unknown').length };
  const loading = inventory.loading || rfile.loading;
  const manage = onManage ?? onDevices;
  const points = new Map([...layout.nodes, layout.hub].map(point => [point.id, point]));
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
        <select aria-label="设备来源" value={filters.source} onChange={event => changeFilter({ source: event.target.value })}><option value="all">全部来源</option><option value="inventory">登记设备</option><option value="rfile">R-File</option></select>
      </div></div>
      {(inventory.error || rfile.error || server.error) && <div role="alert" className="topology-alert">
        {inventory.error && <p>设备清单暂不可用：{inventory.error.message}</p>}{rfile.error && <p>R-File 状态暂不可用：{rfile.error.message}</p>}{server.error && <p>服务端信息暂不可用：{server.error.message}</p>}
      </div>}
      {rfile.data && rfile.data.network.state !== 'online' && <p className="topology-muted">R-File 网络服务{rfile.data.network.state === 'unchecked' ? '正在检查' : '暂不可用'}，设备状态待确认。</p>}
      {loading && nodes.length > 0 && <p className="topology-muted" role="status">正在读取{[inventory.loading && '设备清单', rfile.loading && 'R-File'].filter(Boolean).join('、')}…</p>}
      <div className="topology-canvas-shell">
        <div className="topology-canvas-caption"><Network size={14} /><span>管理与发现关系</span><span className="topology-caption-count">{visible.length} 台设备{size.width < 480 && ' · 可拖动'}</span></div>
        <div className="topology-viewport" ref={viewport} tabIndex={0} aria-label="拓扑画布，可滚动或拖动空白区域"
          onPointerDown={event => {
            if (event.pointerType === 'touch' || event.button !== 0 || (event.target as HTMLElement).closest('button')) return;
            const element = event.currentTarget;
            drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop };
            element.setPointerCapture?.(event.pointerId);
          }} onPointerMove={event => { const start = drag.current; if (start && start.id === event.pointerId) { event.currentTarget.scrollLeft = start.left + start.x - event.clientX; event.currentTarget.scrollTop = start.top + start.y - event.clientY; } }}
          onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}>
          <div className="topology-stage-space" style={{ width: layout.width * zoom, height: layout.height * zoom }}><div className="topology-stage" style={{ width: layout.width, height: layout.height, transform: `scale(${zoom})` }}>
            <svg className="topology-edges" width={layout.width} height={layout.height} aria-hidden="true">{layout.edges.map(edge => {
              const from = points.get(edge.from)!; const to = points.get(edge.to)!;
              const active = selectedId === edge.from || selectedId === edge.to;
              return <path key={edge.to} data-relation={edge.relation} className={active ? 'selected' : ''} strokeDasharray={edge.relation === 'gateway' ? undefined : '5 6'} d={`M ${from.x} ${from.y} C ${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x} ${to.y}`} />;
            })}</svg>
            <article className="topology-node topology-hub" style={{ left: layout.hub.x, top: layout.hub.y }}><Server size={32} strokeWidth={1.4} /><div><strong title={server.data?.hostname}>{server.data?.hostname || '当前服务端'}</strong><span>当前 R-Link 服务端</span><small>{server.error ? '连接待确认' : server.loading ? '正在读取…' : '管理 / 发现中心'}</small></div></article>
            {layout.nodes.map(node => { const Icon = deviceIcons[node.type]; return <button key={node.id} ref={element => { if (element) nodeButtons.current.set(node.id, element); else nodeButtons.current.delete(node.id); }}
              className={`topology-node${selectedId === node.id ? ' selected' : ''}`} style={{ left: node.x, top: node.y }} aria-label={`查看设备：${node.name}`} aria-pressed={selectedId === node.id} title={`${node.name} · ${node.sourceLabel}`} onClick={() => setSelectedId(node.id)}>
              <Icon size={33} strokeWidth={1.4} /><span className="topology-node-copy"><strong>{node.name}</strong><span>{node.subtitle}</span><StatusBadge node={node} /><small>{node.sourceLabel}</small></span>
            </button>; })}
          </div></div>
        </div>
        {loading && !nodes.length && <div className="topology-empty" role="status"><RefreshCw size={24} className="animate-spin" /><h3>正在读取设备…</h3></div>}
        {!loading && !visible.length && <div className="topology-empty"><Network size={32} strokeWidth={1.3} /><h3>{nodes.length ? '没有符合筛选条件的设备' : inventory.error || rfile.error ? '设备信息暂不可用' : '尚未发现设备'}</h3><p>{nodes.length ? '调整搜索或筛选条件以查看其他设备。' : '添加设备，或连接已有的 R-File 网络服务。'}</p>{nodes.length ? <button className="topology-button" onClick={() => changeFilter({ query: '', status: 'all', type: 'all', source: 'all' })}>清除筛选</button> : onRFile && <button className="topology-button" onClick={onRFile}>查看 R-File 服务</button>}</div>}
        <div className="topology-canvas-footer"><div className="topology-legend">{(['online', 'offline', 'unknown'] as Presence[]).map(status => <span key={status}><i className={`topology-dot is-${status}`} />{presenceLabels[status]}</span>)}</div>
          <div className="topology-zoom"><button aria-label="缩小" disabled={zoom <= 0.35} onClick={() => setManualZoom(Math.max(0.35, zoom - 0.15))}><Minus size={16} /></button><output aria-label="缩放比例">{Math.round(zoom * 100)}%</output><button aria-label="放大" disabled={zoom >= 1.5} onClick={() => setManualZoom(Math.min(1.5, zoom + 0.15))}><Plus size={16} /></button><button aria-label="适应视图" title="适应视图" onClick={resetView}><Maximize size={16} /></button></div>
        </div>
      </div>
      <div className="topology-footnote"><span>连线表示登记、网关归属或发现关系；当前服务端不计入设备数。</span>{onStorage && <button onClick={onStorage}><Folder size={14} />服务端共享文件</button>}</div>
    </div>
    {selected && <TopologyDetails node={selected} onClose={close} onSsh={onSsh} onManage={onManage} onRFile={onRFile} />}
  </section>;
}
