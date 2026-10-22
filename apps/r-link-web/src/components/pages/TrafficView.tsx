import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { clashApi, type ClashStatus } from '../../api/clash';
import {
  calculateTrafficDelta,
  connectionHost,
  connectionProcess,
  connectionProtocol,
  connectionSource,
  filterTrafficConnections,
  trafficApi,
  type ClashTrafficConnection,
  type ClashTrafficSnapshot,
  type TrafficConnectionRate,
  type TrafficDelta,
} from '../../api/traffic';
import { usePolling } from '../../api/usePolling';
import { NetworkMonitor } from '../NetworkMonitor';
import { QosManager } from '../QosManager';
import { serviceButton as button, serviceInput, ServiceMessage } from '../common/ServiceControls';

const card = 'rounded-xl border border-[var(--c-800)] bg-[var(--c-900)] p-4';
const muted = 'text-sm text-[var(--c-400)]';
const WAITING_MESSAGE = '等待下一帧重新采样以计算真实速率…';
const MAX_HISTORY = 60;
const TOP_N = 5;

export interface TrafficViewProps {
  /** Lets the host application open the Clash configuration page. */
  onConfigureClash?: () => void;
}

type TrafficPollingState = {
  data: ClashTrafficSnapshot | null;
  loading: boolean;
  error: Error | null;
};

type TrafficHistoryPoint = {
  sampledAt: number;
  time: string;
  downloadBps: number;
  uploadBps: number;
};

type ConnectionSort = 'download' | 'upload' | 'target' | 'source' | 'start';

type PendingDisconnect = {
  ids: string[];
  labels: string[];
  sourceId: string;
  targetKey: string;
};

function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  if (Math.abs(value) < 1024) return `${value.toFixed(0)} B`;
  const units = ['KiB', 'MiB', 'GiB', 'TiB'];
  let amount = value;
  let unit = -1;
  while (Math.abs(amount) >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(Math.abs(amount) >= 100 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '等待采样';
  return `${formatBytes(value)}/s`;
}

function formatTime(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '未知';
  const date = typeof value === 'number' && value < 10_000_000_000 ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleTimeString();
}

function connectionTargetLabel(connection: ClashTrafficConnection): string {
  const target = connectionHost(connection);
  const port = connection.metadata?.destinationPort;
  return port === undefined || port === null || port === '' ? target : `${target}:${port}`;
}

function connectionDisplayLabel(connection: ClashTrafficConnection): string {
  return `${connectionTargetLabel(connection)} · ${connectionSource(connection)}`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

/** At most one snapshot request is in flight; stale generations cannot update a new target. */
function useTrafficPolling(enabled: boolean, targetKey: string, preserveWhenDisabled: boolean) {
  const [state, setState] = useState<TrafficPollingState>({ data: null, loading: false, error: null });
  const pending = useRef<{ generation: number; promise: Promise<void> } | null>(null);
  const controller = useRef<{ generation: number; controller: AbortController } | null>(null);
  const generation = useRef(0);
  const activeGeneration = useRef(0);
  const mounted = useRef(false);
  const previousTargetKey = useRef(targetKey);

  const refetch = useCallback(async () => {
    const requestGeneration = activeGeneration.current;
    if (!mounted.current || requestGeneration === 0) return;
    if (pending.current?.generation === requestGeneration) return pending.current.promise;
    const request = (async () => {
      const nextController = new AbortController();
      controller.current = { generation: requestGeneration, controller: nextController };
      const canUpdate = () => mounted.current && activeGeneration.current === requestGeneration && !nextController.signal.aborted;
      setState(previous => ({ ...previous, loading: true, error: null }));
      try {
        const data = await trafficApi.snapshot(nextController.signal);
        if (canUpdate()) setState({ data, loading: false, error: null });
      } catch (error) {
        if (isAbortError(error) || !canUpdate()) return;
        setState({ data: null, loading: false, error: error instanceof Error ? error : new Error(String(error)) });
      } finally {
        if (controller.current?.generation === requestGeneration && controller.current.controller === nextController) controller.current = null;
      }
    })();
    pending.current = { generation: requestGeneration, promise: request };
    try {
      await request;
    } finally {
      if (pending.current?.promise === request) pending.current = null;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const requestGeneration = ++generation.current;
    const targetChanged = previousTargetKey.current !== targetKey;
    previousTargetKey.current = targetKey;
    activeGeneration.current = requestGeneration;
    if (!enabled) {
      if (!preserveWhenDisabled || targetChanged) setState({ data: null, loading: false, error: null });
      else setState(previous => ({ ...previous, loading: false }));
      return () => {
        if (activeGeneration.current === requestGeneration) activeGeneration.current = 0;
        if (controller.current?.generation === requestGeneration) controller.current.controller.abort();
      };
    }
    setState({ data: null, loading: true, error: null });
    void refetch();
    const timer = window.setInterval(() => void refetch(), 2000);
    return () => {
      window.clearInterval(timer);
      if (activeGeneration.current === requestGeneration) activeGeneration.current = 0;
      if (controller.current?.generation === requestGeneration) controller.current.controller.abort();
    };
  }, [enabled, preserveWhenDisabled, refetch, targetKey]);

  useEffect(() => () => {
    mounted.current = false;
    activeGeneration.current = 0;
    controller.current?.controller.abort();
  }, []);

  return { ...state, refetch };
}

function connectionRate(rates: Record<string, TrafficConnectionRate | null>, id: string): TrafficConnectionRate | null {
  return rates[id] || null;
}

function sortConnections(
  connections: ClashTrafficConnection[],
  sort: ConnectionSort,
  rates: Record<string, TrafficConnectionRate | null>,
): ClashTrafficConnection[] {
  return [...connections].sort((left, right) => {
    const leftRate = connectionRate(rates, left.id);
    const rightRate = connectionRate(rates, right.id);
    if (sort === 'download') return (rightRate?.downloadBps ?? -1) - (leftRate?.downloadBps ?? -1);
    if (sort === 'upload') return (rightRate?.uploadBps ?? -1) - (leftRate?.uploadBps ?? -1);
    if (sort === 'source') return connectionSource(left).localeCompare(connectionSource(right));
    if (sort === 'start') return String(right.start || '').localeCompare(String(left.start || ''));
    return connectionHost(left).localeCompare(connectionHost(right));
  });
}

type Aggregate = { name: string; count: number; pending: number; downloadBps: number; uploadBps: number };

function aggregateConnections(
  connections: ClashTrafficConnection[],
  rates: Record<string, TrafficConnectionRate | null>,
  name: (connection: ClashTrafficConnection) => string,
): Aggregate[] {
  const groups = new Map<string, Aggregate>();
  for (const connection of connections) {
    const key = name(connection);
    const rate = connectionRate(rates, connection.id);
    const current = groups.get(key) || { name: key, count: 0, pending: 0, downloadBps: 0, uploadBps: 0 };
    current.count += 1;
    if (!rate) {
      current.pending += 1;
    } else {
      current.downloadBps += rate.downloadBps;
      current.uploadBps += rate.uploadBps;
    }
    groups.set(key, current);
  }
  return [...groups.values()]
    .sort((left, right) => (right.downloadBps + right.uploadBps) - (left.downloadBps + left.uploadBps))
    .slice(0, TOP_N);
}

function statusLabel(status: ClashStatus | null, loading: boolean, error: Error | null): string {
  if (!status) return error ? '状态不可用' : loading ? '正在读取 Clash 状态…' : '尚未收到 Clash 状态';
  if (!status.configured) return '未配置';
  return status.connected ? '已连接' : '未连接';
}

function ConnectionCard({
  connection,
  rate,
  selected,
  disabled,
  onToggle,
  onDisconnect,
}: {
  connection: ClashTrafficConnection;
  rate: TrafficConnectionRate | null;
  selected: boolean;
  disabled: boolean;
  onToggle: () => void;
  onDisconnect: () => void;
}) {
  const target = connectionTargetLabel(connection);
  return <tr className="border-t border-[var(--c-800)] align-top">
    <td className="p-3"><input type="checkbox" aria-label={`选择 ${target}`} checked={selected} disabled={disabled} onChange={onToggle} /></td>
    <td className="p-3 min-w-48 max-w-80 break-all"><strong>{target}</strong><p className="mt-1 text-xs text-[var(--c-500)]">{connection.rule || '规则未知'} · {formatTime(connection.start)}</p></td>
    <td className="p-3 min-w-48 max-w-80 break-all text-sm"><div>{connectionSource(connection)}</div><div className="mt-1 text-xs text-[var(--c-500)]">{connectionProcess(connection)}</div></td>
    <td className="p-3 whitespace-nowrap text-sm">{connectionProtocol(connection)}</td>
    <td className="p-3 whitespace-nowrap text-sm"><div>{rate ? formatRate(rate.downloadBps) : '等待采样'}</div><div className="mt-1 text-xs text-[var(--c-500)]">累计 {formatBytes(connection.download)}</div></td>
    <td className="p-3 whitespace-nowrap text-sm"><div>{rate ? formatRate(rate.uploadBps) : '等待采样'}</div><div className="mt-1 text-xs text-[var(--c-500)]">累计 {formatBytes(connection.upload)}</div></td>
    <td className="p-3 whitespace-nowrap"><button className={button} disabled={disabled} onClick={onDisconnect}>断开连接</button></td>
  </tr>;
}

function StatsList({ title, items }: { title: string; items: Aggregate[] }) {
  return <div className={`${card} space-y-3`}>
    <div><h3 className="font-semibold">{title}</h3><p className="text-xs text-[var(--c-500)]">按当前连接快照聚合，最多显示 {TOP_N} 项。</p></div>
    {items.length === 0 ? <p className={muted}>暂无连接数据。</p> : <ol className="space-y-2 text-sm">{items.map(item => {
      const waitingLabel = item.pending === item.count ? '等待采样' : '部分连接待采样';
      return <li key={item.name} className="flex flex-wrap justify-between gap-2"><span className="min-w-0 break-all">{item.name} <span className="text-[var(--c-500)]">({item.count})</span></span><span className="whitespace-nowrap text-[var(--c-400)]">{item.pending > 0 && <span className="mr-2">{waitingLabel}</span>}{item.pending < item.count && <>↓ {formatRate(item.downloadBps)} · ↑ {formatRate(item.uploadBps)}</>}</span></li>;
    })}</ol>}
  </div>;
}

function StatusGate({ status, loading, error, onConfigureClash }: { status: ClashStatus | null; loading: boolean; error: Error | null; onConfigureClash?: () => void }) {
  if (!status) return <div className={card}><p className={muted}>{statusLabel(status, loading, error)}</p>{error && <ServiceMessage error={error.message} />}</div>;
  if (!status.configured) return <div className={card}><h3 className="font-semibold">Clash 流量</h3><p className="mt-2 text-sm text-[var(--c-400)]">Clash 尚未配置，请先配置控制器。</p>{onConfigureClash && <button className={`${button} mt-3`} onClick={onConfigureClash}>前往 Clash 配置</button>}</div>;
  if (!status.connected) return <div className={card}><h3 className="font-semibold">Clash 流量</h3><p className="mt-2 text-sm text-[var(--c-400)]">Clash 当前未连接，暂时无法读取代理流量。</p>{status.error && <ServiceMessage error={status.error} />}</div>;
  return null;
}

function TrafficChart({ history }: { history: TrafficHistoryPoint[] }) {
  return <div className="h-[260px] mt-3">
    {history.length < 2 ? <p className={muted}>{WAITING_MESSAGE}</p> : <ResponsiveContainer width="100%" height="100%"><AreaChart data={history}>
      <XAxis dataKey="time" fontSize={10} /><YAxis fontSize={10} tickFormatter={value => formatRate(Number(value))} /><Tooltip formatter={(value: number) => formatRate(value)} />
      <Area type="linear" dataKey="downloadBps" name="下载" stroke="#3b82f6" fill="#3b82f622" isAnimationActive={false} />
      <Area type="linear" dataKey="uploadBps" name="上传" stroke="#10b981" fill="#10b98122" isAnimationActive={false} />
    </AreaChart></ResponsiveContainer>}
  </div>;
}

export function TrafficView({ onConfigureClash }: TrafficViewProps) {
  const { data: status, loading: statusLoading, error: statusError, refetch: refetchStatus } = usePolling(useCallback((signal: AbortSignal) => clashApi.status(signal), []), 5000);
  const connected = Boolean(status?.configured && status.connected);
  const targetKey = status?.controller_url || '';
  const [paused, setPaused] = useState(false);
  const { data: traffic, loading: trafficLoading, error: trafficError, refetch: refetchTraffic } = useTrafficPolling(connected && !paused, targetKey, connected && paused);
  const sourceContext = useRef<{ connected: boolean; sourceId: string | null; targetKey: string }>({ connected, sourceId: traffic?.source_id || null, targetKey });
  sourceContext.current = { connected, sourceId: traffic?.source_id || null, targetKey };
  const previous = useRef<ClashTrafficSnapshot | null>(null);
  const [delta, setDelta] = useState<TrafficDelta | null>(null);
  const [history, setHistory] = useState<TrafficHistoryPoint[]>([]);
  const observedSource = useRef<string | null>(null);
  const [query, setQuery] = useState('');
  const [protocol, setProtocol] = useState('');
  const [sort, setSort] = useState<ConnectionSort>('download');
  const [selected, setSelected] = useState<string[]>([]);
  const [pendingDisconnect, setPendingDisconnect] = useState<PendingDisconnect | null>(null);
  const [disconnectBusy, setDisconnectBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const [actionError, setActionError] = useState('');
  const viewMounted = useRef(true);

  useEffect(() => {
    viewMounted.current = true;
    return () => { viewMounted.current = false; };
  }, []);

  useEffect(() => {
    observedSource.current = null;
    previous.current = null;
    setDelta(null);
    setHistory([]);
    setSelected([]);
    setPendingDisconnect(null);
    setActionMessage('');
    setActionError('');
  }, [connected, targetKey]);

  useEffect(() => {
    if (!connected || trafficError || !traffic) {
      previous.current = null;
      setDelta(null);
      setHistory([]);
      return;
    }
    const sourceChanged = observedSource.current !== null && observedSource.current !== traffic.source_id;
    observedSource.current = traffic.source_id;
    if (sourceChanged) {
      previous.current = null;
      setDelta(null);
      setHistory([]);
      setSelected([]);
      setPendingDisconnect(null);
      setActionMessage('');
      setActionError('');
    }
    const nextDelta = calculateTrafficDelta(previous.current, traffic);
    previous.current = traffic;
    setDelta(nextDelta);
    if (!nextDelta.ready) {
      setHistory([]);
      return;
    }
    setHistory(previousHistory => [...previousHistory, {
      sampledAt: traffic.sampled_at,
      time: formatTime(traffic.sampled_at),
      downloadBps: nextDelta.downloadBps,
      uploadBps: nextDelta.uploadBps,
    }].slice(-MAX_HISTORY));
  }, [connected, traffic, trafficError]);

  const connections = traffic?.connections || [];
  useEffect(() => {
    const ids = new Set(connections.map(connection => connection.id));
    setSelected(previousSelected => previousSelected.filter(id => ids.has(id)));
  }, [traffic]);

  useEffect(() => {
    if (!pendingDisconnect) return;
    if (!connected || pendingDisconnect.targetKey !== targetKey || !traffic?.source_id || pendingDisconnect.sourceId !== traffic.source_id) {
      setPendingDisconnect(null);
      setSelected([]);
      setActionMessage('');
      setActionError('');
    }
  }, [connected, pendingDisconnect, targetKey, traffic?.source_id]);

  const protocols = useMemo(() => [...new Set(connections.map(connectionProtocol))].sort((left, right) => left.localeCompare(right)), [connections]);
  const visibleConnections = useMemo(
    () => sortConnections(filterTrafficConnections(connections, query, protocol), sort, delta?.connectionRates || {}),
    [connections, delta?.connectionRates, protocol, query, sort],
  );
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const allVisibleSelected = visibleConnections.length > 0 && visibleConnections.every(connection => selectedSet.has(connection.id));
  const appStats = useMemo(() => aggregateConnections(connections, delta?.connectionRates || {}, connectionProcess), [connections, delta?.connectionRates]);
  const targetStats = useMemo(() => aggregateConnections(connections, delta?.connectionRates || {}, connectionHost), [connections, delta?.connectionRates]);

  const selectVisible = () => {
    if (allVisibleSelected) {
      const visibleIds = new Set(visibleConnections.map(connection => connection.id));
      setSelected(previousSelected => previousSelected.filter(id => !visibleIds.has(id)));
    } else {
      setSelected(previousSelected => [...new Set([...previousSelected, ...visibleConnections.map(connection => connection.id)])]);
    }
  };

  const requestDisconnect = (ids: string[]) => {
    const uniqueIds = [...new Set(ids)].filter(Boolean);
    if (uniqueIds.length === 0) return;
    const sourceId = traffic?.source_id;
    if (!connected || !sourceId) {
      setActionError('流量来源不可用，请刷新后重试。');
      return;
    }
    const labels = uniqueIds.map(id => {
      const connection = connections.find(candidate => candidate.id === id);
      return connection ? connectionDisplayLabel(connection) : id;
    });
    setActionError('');
    setActionMessage('');
    setPendingDisconnect({ ids: uniqueIds, labels, sourceId, targetKey });
  };

  const confirmDisconnect = async () => {
    if (!pendingDisconnect || disconnectBusy) return;
    const pending = pendingDisconnect;
    setDisconnectBusy(true);
    setActionError('');
    setActionMessage('');
    const isCurrentSource = () => viewMounted.current && sourceContext.current.connected && sourceContext.current.sourceId === pending.sourceId && sourceContext.current.targetKey === pending.targetKey;
    if (!isCurrentSource()) {
      setPendingDisconnect(null);
      setSelected([]);
      setActionMessage('');
      setActionError('');
      setDisconnectBusy(false);
      return;
    }
    try {
      if (pending.ids.length === 1) {
        try {
          await clashApi.closeConnection(pending.ids[0], pending.sourceId);
          if (!isCurrentSource()) return;
          setActionMessage(`已请求断开：${pending.labels[0]}`);
          setSelected(previousSelected => previousSelected.filter(id => id !== pending.ids[0]));
        } catch (error) {
          if (!isCurrentSource()) return;
          setActionError(`断开失败（${pending.labels[0]}）：${errorMessage(error)}`);
        }
      } else {
        const results: PromiseSettledResult<unknown>[] = [];
        for (let index = 0; index < pending.ids.length; index += 4) {
          if (!isCurrentSource()) return;
          const batch = pending.ids.slice(index, index + 4);
          results.push(...await Promise.allSettled(batch.map(id => clashApi.closeConnection(id, pending.sourceId))));
        }
        if (!isCurrentSource()) return;
        const succeeded = results.filter(result => result.status === 'fulfilled').length;
        const failures = results.flatMap((result, index) => result.status === 'rejected' ? [`${pending.labels[index]}：${errorMessage(result.reason)}`] : []);
        if (succeeded > 0) setActionMessage(`已请求断开 ${succeeded} 条连接。`);
        if (failures.length > 0) setActionError(`部分连接断开失败：${failures.join('；')}`);
        const successfulIds = results.flatMap((result, index) => result.status === 'fulfilled' ? [pending.ids[index]] : []);
        setSelected(previousSelected => previousSelected.filter(id => !successfulIds.includes(id)));
      }
      if (isCurrentSource()) await refetchTraffic();
    } finally {
      if (viewMounted.current) {
        setPendingDisconnect(null);
        setDisconnectBusy(false);
      }
    }
  };

  const waiting = connected && (!delta || !delta.ready);
  const totalConnections = traffic?.total_connections ?? connections.length;
  const sourceDescription = status?.controller_url ? `Clash 控制器 ${status.controller_url}` : 'Clash 控制器';

  return <section className="space-y-5 pb-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><h2 className="text-xl font-bold">网络流量管理</h2><p className="mt-2 text-sm text-[var(--c-400)]">查看服务端网卡和 Clash 代理流量，筛选并管理当前连接。</p></div>
      <div className="flex flex-wrap gap-2">
        <button className={button} disabled={statusLoading || disconnectBusy} onClick={() => { void refetchStatus(); if (connected) void refetchTraffic(); }}>手动刷新</button>
        <button className={button} disabled={!connected || disconnectBusy} onClick={() => setPaused(previousPaused => !previousPaused)}>{paused ? '继续 Clash 采样' : '暂停 Clash 采样'}</button>
      </div>
    </div>

    <div className="rounded-xl border border-[var(--c-800)] bg-[var(--c-900)] p-4">
      <h3 className="font-semibold">数据来源</h3>
      <p className="mt-2 text-sm text-[var(--c-400)]">Clash 代理流量：{sourceDescription} 的当前连接快照。</p>
      <p className="mt-1 text-sm text-[var(--c-400)]">服务端网卡总流量：服务端真实网卡累计计数。</p>
    </div>

    <QosManager />

    <StatusGate status={status} loading={statusLoading} error={statusError} onConfigureClash={onConfigureClash} />

    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold">Clash 连接流量</h3><p className={muted}>{paused ? '采样已暂停，页面保留最后一帧。' : waiting ? WAITING_MESSAGE : `数据源：${sourceDescription}`}</p></div><span className="text-sm text-[var(--c-500)]">{traffic?.sampled_at ? `采样：${formatTime(traffic.sampled_at)}` : '暂无采样'}</span></div>
      <ServiceMessage error={statusError?.message || trafficError?.message || actionError}>{actionMessage && <p role="status" className="text-emerald-400">{actionMessage}</p>}</ServiceMessage>
      {trafficLoading && <p role="status" className={muted}>正在读取 Clash 流量…</p>}
      {traffic && <>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className={card}><dt className={muted}>累计下载</dt><dd className="mt-1 text-lg font-semibold">{formatBytes(traffic.downloadTotal)}</dd></div>
          <div className={card}><dt className={muted}>累计上传</dt><dd className="mt-1 text-lg font-semibold">{formatBytes(traffic.uploadTotal)}</dd></div>
          <div className={card}><dt className={muted}>当前连接</dt><dd className="mt-1 text-lg font-semibold">{connections.length}{traffic.truncated ? '+' : ''} <span className="text-sm font-normal text-[var(--c-500)]">/ 服务端 {totalConnections}</span></dd></div>
          <div className={card}><dt className={muted}>当前下载 / 上传</dt><dd className="mt-1 text-lg font-semibold">{delta?.ready ? `${formatRate(delta.downloadBps)} · ${formatRate(delta.uploadBps)}` : '等待采样'}</dd></div>
        </div>
        {traffic.truncated && <p className="text-xs text-amber-400">连接列表被服务端截断，连接管理及应用、目标统计仅覆盖当前返回的连接；总连接数仍按服务端报告显示。</p>}
        <div className={card}><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">最近 60 个速率样本</h3><p className={muted}>速率在连续采样后显示。</p></div><span className="text-xs text-[var(--c-500)]">下载 / 上传 B/s</span></div><TrafficChart history={history} /></div>

        <div className="grid gap-4 lg:grid-cols-2"><StatsList title="按应用 / 进程" items={appStats} /><StatsList title="按目标" items={targetStats} /></div>

        <div className={`${card} space-y-4`}>
          <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="font-semibold">连接列表</h3><p className={muted}>断开操作会作用于当前 Clash。</p></div><div className="flex flex-wrap gap-2"><button className={button} disabled={disconnectBusy || selected.length === 0} onClick={() => requestDisconnect(selected)}>断开选中（{selected.length}）</button></div></div>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_12rem_12rem]"><label className="text-sm">搜索目标、来源或进程<input className={serviceInput} aria-label="搜索目标、来源或进程" value={query} onChange={event => setQuery(event.target.value)} placeholder="host / source / process" /></label><label className="text-sm">协议<select className={serviceInput} aria-label="协议筛选" value={protocol} onChange={event => setProtocol(event.target.value)}><option value="">全部协议</option>{protocols.map(value => <option key={value} value={value}>{value}</option>)}</select></label><label className="text-sm">排序<select className={serviceInput} aria-label="连接排序" value={sort} onChange={event => setSort(event.target.value as ConnectionSort)}><option value="download">下载速率</option><option value="upload">上传速率</option><option value="target">目标</option><option value="source">来源</option><option value="start">开始时间</option></select></label></div>
          {connections.length === 0 ? <div className="rounded-lg border border-[var(--c-800)] p-8 text-center"><p className={muted}>当前没有活动连接。</p></div> : visibleConnections.length === 0 ? <div className="rounded-lg border border-[var(--c-800)] p-8 text-center"><p className={muted}>没有符合当前搜索或协议筛选的连接。</p></div> : <div className="overflow-x-auto rounded-lg border border-[var(--c-800)]"><table className="w-full min-w-[920px] text-left"><thead className="bg-[var(--c-950)] text-xs text-[var(--c-400)]"><tr><th className="p-3"><input type="checkbox" aria-label="选择全部可见连接" checked={allVisibleSelected} onChange={selectVisible} disabled={disconnectBusy} /></th><th className="p-3">目标</th><th className="p-3">来源 / 进程</th><th className="p-3">协议</th><th className="p-3">下载速率</th><th className="p-3">上传速率</th><th className="p-3">操作</th></tr></thead><tbody>{visibleConnections.map(connection => <ConnectionCard key={connection.id} connection={connection} rate={connectionRate(delta?.connectionRates || {}, connection.id)} selected={selectedSet.has(connection.id)} disabled={disconnectBusy} onToggle={() => setSelected(previousSelected => previousSelected.includes(connection.id) ? previousSelected.filter(id => id !== connection.id) : [...previousSelected, connection.id])} onDisconnect={() => requestDisconnect([connection.id])} />)}</tbody></table></div>}
        </div>
      </>}
    </div>

    <div><div className="mb-3"><h3 className="text-lg font-semibold">服务端网卡总流量</h3><p className={muted}>读取服务端真实网卡累计计数，与上方 Clash 代理流量分开显示。</p></div><NetworkMonitor /></div>

    {pendingDisconnect && <div role="dialog" aria-modal="true" aria-label="确认断开 Clash 连接" className="rounded-xl border border-red-500/40 bg-[var(--c-900)] p-4 space-y-3"><div><h3 className="font-semibold">确认断开连接</h3><p className="mt-2 text-sm text-[var(--c-400)]">将关闭 {pendingDisconnect.ids.length} 条连接：</p><ul className="mt-2 list-disc pl-5 text-sm">{pendingDisconnect.labels.slice(0, 10).map((label, index) => <li key={`${label}-${index}`} className="break-all">{label}</li>)}{pendingDisconnect.labels.length > 10 && <li>其余 {pendingDisconnect.labels.length - 10} 条连接</li>}</ul></div><div className="flex gap-2"><button className={button} disabled={disconnectBusy} onClick={() => void confirmDisconnect()}>确认断开</button><button className={button} disabled={disconnectBusy} onClick={() => setPendingDisconnect(null)}>取消</button></div></div>}
  </section>;
}

export default TrafficView;
