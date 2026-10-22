import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  clashApi,
  type ClashConfigs,
  type ClashManagedStatus,
  type ClashMode,
  type ClashLogLevel,
  type ClashProfile,
  type ClashProvider,
  type ClashProxy,
  type ClashStatus,
} from '../../api/clash';
import { trafficApi, type ClashTrafficConnection } from '../../api/traffic';
import { usePolling } from '../../api/usePolling';
import { ServiceField, ServiceMessage, serviceButton as button, serviceInput, useServiceAction } from '../common/ServiceControls';

type ClashTab = 'overview' | 'proxies' | 'rules' | 'connections' | 'providers' | 'profiles';

const tabs: { id: ClashTab; label: string }[] = [
  { id: 'overview', label: '概览与配置' },
  { id: 'proxies', label: '代理组' },
  { id: 'rules', label: '规则' },
  { id: 'connections', label: '连接' },
  { id: 'providers', label: '提供商' },
  { id: 'profiles', label: '受管配置' },
];

const card = 'rounded-xl border border-[var(--c-800)] bg-[var(--c-900)] p-4';
const muted = 'text-sm text-[var(--c-400)]';

function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  if (Math.abs(value) < 1024) return `${value} B`;
  const units = ['KiB', 'MiB', 'GiB', 'TiB'];
  let amount = value;
  let unit = -1;
  while (Math.abs(amount) >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(amount >= 100 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function numeric(value: number | string | null | undefined): number {
  const result = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(result) ? result : 0;
}

function formatDate(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '未知';
  const date = typeof value === 'number' && value < 10_000_000_000 ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function serverHost(raw: string): string {
  try {
    return new URL(raw).hostname || raw;
  } catch {
    return raw.replace(/^[a-z][a-z\d+.-]*:\/\//i, '').split('/')[0] || raw;
  }
}

function proxyAddress(host: string, port: number | null | undefined): string {
  return port === null || port === undefined || !port ? '未提供' : `${host}:${port}`;
}

function isSelectableProxyGroup(proxy: ClashProxy): boolean {
  // Mihomo only accepts manual PUT selection for selector groups. URLTest,
  // Fallback and LoadBalance choose their member automatically.
  return Array.isArray(proxy.all) && proxy.type.toLowerCase() === 'selector';
}

function proxyAvailability(proxy: ClashProxy): string {
  if (proxy.alive === true) return '可用';
  if (proxy.alive === false) return '不可用';
  return '未知';
}

function connectionState(status: ClashStatus | null, loading: boolean, error: Error | null): string {
  if (status) {
    if (!status.configured) return '未配置';
    return status.connected ? '已连接' : '未连接';
  }
  if (error) return '状态不可用';
  return loading ? '正在读取状态…' : '尚未收到状态';
}

function ConnectedGate({ status }: { status: ClashStatus | null }) {
  if (!status) return <p className={muted}>等待 Clash 状态返回后读取此面板。</p>;
  if (!status.configured) return <p className={muted}>请先保存 API 控制器地址与密码，Clash 尚未配置。</p>;
  if (!status.connected) return <p className={muted}>Clash 当前未连接，暂不读取代理组、规则、连接或提供商数据。</p>;
  return null;
}

function ConfigPanel({ status }: { status: ClashStatus }) {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => clashApi.configs(signal), []));
  const action = useServiceAction();
  const update = (input: Partial<Pick<ClashConfigs, 'mode' | 'log_level'>>) => {
    void action.run(async () => {
      await clashApi.updateConfigs(input);
      await refetch();
    });
  };
  if (!status.connected) return <div className={card}><h3 className="font-semibold">代理运行配置</h3><div className="mt-3"><ConnectedGate status={status} /></div></div>;
  return <div className={`${card} space-y-4`}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="font-semibold">代理运行配置</h3><p className={muted}>当前内核运行在 API 服务器主机，配置变更直接作用于该主机。</p></div>
      <button className={button} disabled={loading || action.busy} onClick={() => void refetch()}>刷新配置</button>
    </div>
    <ServiceMessage error={action.error || error?.message} />
    {loading && <p role="status" className={muted}>正在读取配置…</p>}
    {data && <>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-sm">运行模式
          <select aria-label="运行模式" className={serviceInput} disabled={action.busy} value={data.mode || ''} onChange={event => update({ mode: event.target.value as ClashMode })}>
            {!data.mode && <option value="">未提供</option>}
            <option value="rule">规则（Rule）</option><option value="global">全局（Global）</option><option value="direct">直连（Direct）</option>
          </select>
        </label>
        <label className="text-sm">日志级别
          <select aria-label="日志级别" className={serviceInput} disabled={action.busy} value={data.log_level || ''} onChange={event => update({ log_level: event.target.value as ClashLogLevel })}>
            {!data.log_level && <option value="">未提供</option>}
            <option value="silent">静默</option><option value="error">错误</option><option value="warning">警告</option><option value="info">信息</option><option value="debug">调试</option>
          </select>
        </label>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <div><dt className="text-[var(--c-500)]">混合代理</dt><dd className="font-mono">{proxyAddress(serverHost(status.controller_url), data.mixed_port)}</dd></div>
        <div><dt className="text-[var(--c-500)]">HTTP 代理</dt><dd className="font-mono">{proxyAddress(serverHost(status.controller_url), data.port)}</dd></div>
        <div><dt className="text-[var(--c-500)]">SOCKS 代理</dt><dd className="font-mono">{proxyAddress(serverHost(status.controller_url), data.socks_port)}</dd></div>
        <div><dt className="text-[var(--c-500)]">允许局域网</dt><dd>{data.allow_lan ? '是' : '否'}</dd></div>
        <div><dt className="text-[var(--c-500)]">TUN</dt><dd>{data.tun_enabled ? '已启用' : '未启用'}</dd></div>
      </dl>
      <p className="text-xs text-[var(--c-500)]">R-Link 不会自动修改本机系统代理，也不会替你开关 TUN。上方地址和端口是 API 服务器主机对外报告的监听信息。</p>
    </>}
  </div>;
}

function ProxiesPanel() {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => clashApi.proxies(signal), []), 5000);
  const [delays, setDelays] = useState<Record<string, number | null>>({});
  const action = useServiceAction();
  const groups = useMemo(() => Object.entries(data?.proxies || {}).filter(([, proxy]) => isSelectableProxyGroup(proxy)), [data]);
  const automaticGroups = useMemo(() => Object.entries(data?.proxies || {}).filter(([, proxy]) => Array.isArray(proxy.all) && !isSelectableProxyGroup(proxy)), [data]);
  const leaves = useMemo(() => Object.entries(data?.proxies || {}).filter(([, proxy]) => !Array.isArray(proxy.all)), [data]);
  const choose = (group: string, name: string) => {
    void action.run(async () => {
      await clashApi.selectProxy(group, name);
      await refetch();
    });
  };
  const testDelay = (group: string) => {
    void action.run(async () => {
      const result = await clashApi.proxyDelay(group);
      setDelays(previous => ({ ...previous, [group]: result.delay }));
    });
  };
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">代理组</h3><p className={muted}>选择节点后由 API 服务器切换；延迟测试只在你点击时执行。</p></div><button className={button} disabled={loading || action.busy} onClick={() => void refetch()}>刷新代理组</button></div>
    <ServiceMessage error={action.error || error?.message} />
    {loading && <p role="status" className={muted}>正在读取代理组…</p>}
    {!loading && data && groups.length === 0 && <p className={muted}>服务端没有返回可手动选择的 Selector 代理组。</p>}
    <div className="grid gap-4 lg:grid-cols-2">
      {groups.map(([group, proxy]) => {
        const options = proxy.all || [];
        const value = proxy.now || '';
        return <article key={group} className={card}>
          <div className="flex flex-wrap justify-between gap-2"><strong>{group}</strong><span className={proxy.alive === true ? 'text-emerald-400' : proxy.alive === false ? 'text-red-400' : 'text-[var(--c-400)]'}>{proxy.type} · {proxyAvailability(proxy)}</span></div>
          <label className="mt-3 block text-sm">当前节点
            <select aria-label={`${group} 节点`} className={serviceInput} value={value} disabled={action.busy || options.length === 0} onChange={event => choose(group, event.target.value)}>
              {options.length === 0 && <option value="">暂无节点</option>}
              {options.length > 0 && !proxy.now && <option value="">未选择</option>}
              {options.map(name => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm"><button className={button} disabled={action.busy || !value} onClick={() => testDelay(group)}>测试延迟</button>{delays[group] !== undefined && <span role="status">{delays[group] === null ? '测试失败' : `${delays[group]} ms`}</span>}</div>
          {proxy.history && proxy.history.length > 0 && <p className="mt-3 text-xs text-[var(--c-500)]">最近延迟：{proxy.history.slice(-3).map(item => `${item.delay} ms`).join('、')}</p>}
        </article>;
      })}
    </div>
    {automaticGroups.length > 0 && <div className={`${card} space-y-2`}><h4 className="font-semibold">自动选择组</h4><p className={muted}>URLTest、Fallback、LoadBalance 等由内核自动选择，R-Link 只展示当前节点。</p><div className="flex flex-wrap gap-2">{automaticGroups.map(([name, proxy]) => <span key={name} className="rounded border border-[var(--c-700)] px-2 py-1 text-sm"><span className="font-mono">{name}</span> · {proxy.type} · {proxy.now || '未选择'} · {proxyAvailability(proxy)}</span>)}</div></div>}
    {leaves.length > 0 && <div className={`${card} space-y-2`}><h4 className="font-semibold">叶节点</h4><p className={muted}>DIRECT、REJECT 等非选择器节点仅展示状态。</p><div className="flex flex-wrap gap-2">{leaves.map(([name, proxy]) => <span key={name} className="rounded border border-[var(--c-700)] px-2 py-1 text-sm"><span className="font-mono">{name}</span> · {proxy.type} · {proxyAvailability(proxy)}</span>)}</div></div>}
  </div>;
}

function RulesPanel() {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => clashApi.rules(signal), []));
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">规则</h3><p className={muted}>只读展示 API 服务器当前加载的匹配规则。</p></div><button className={button} disabled={loading} onClick={() => void refetch()}>刷新规则</button></div>
    {error && <ServiceMessage error={error.message} />}
    {loading && <p role="status" className={muted}>正在读取规则…</p>}
    {data && data.rules.length === 0 && <p className={muted}>当前没有规则。</p>}
    {data && data.rules.length > 0 && <div className="overflow-x-auto rounded-xl border border-[var(--c-800)]"><table className="w-full text-left text-sm"><thead className="border-b border-[var(--c-800)] text-[var(--c-400)]"><tr><th className="p-3">类型</th><th className="p-3">匹配</th><th className="p-3">代理</th></tr></thead><tbody>{data.rules.map((rule, index) => <tr key={`${rule.type}-${rule.payload}-${index}`} className="border-b border-[var(--c-800)] last:border-0"><td className="p-3 whitespace-nowrap">{rule.type}</td><td className="p-3 break-all">{rule.payload}</td><td className="p-3 break-all">{rule.proxy}</td></tr>)}</tbody></table></div>}
  </div>;
}

function connectionTarget(connection: ClashTrafficConnection): string {
  const metadata = connection.metadata;
  if (!metadata) return '未知目标';
  return metadata.host || `${metadata.destinationIP}:${metadata.destinationPort}`;
}

function ConnectionsPanel() {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => trafficApi.snapshot(signal), []), 3000);
  const action = useServiceAction();
  const [confirmAll, setConfirmAll] = useState<{ sourceId: string; count: number } | null>(null);
  useEffect(() => {
    if (confirmAll && confirmAll.sourceId !== data?.source_id) setConfirmAll(null);
  }, [confirmAll, data?.source_id]);
  const closeOne = (id: string) => void action.run(async () => {
    if (!data?.source_id) throw new Error('流量来源不可用，请刷新后重试');
    await clashApi.closeConnection(id, data.source_id); await refetch();
  });
  const closeAll = () => void action.run(async () => {
    if (!confirmAll || confirmAll.sourceId !== data?.source_id) throw new Error('流量来源已变化，请重新确认');
    await clashApi.closeAllConnections(confirmAll.sourceId); setConfirmAll(null); await refetch();
  });
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">连接快照</h3><p className={muted}>快照和累计字节数来自 API 服务器；关闭操作需要明确点击确认。</p></div><div className="flex flex-wrap gap-2"><button className={button} disabled={loading || action.busy} onClick={() => void refetch()}>刷新连接</button>{data && data.connections.length > 0 && <button className={button} disabled={action.busy} onClick={() => setConfirmAll({ sourceId: data.source_id, count: data.total_connections })}>关闭全部连接</button>}</div></div>
    <ServiceMessage error={action.error || error?.message} />
    {confirmAll && <div role="dialog" aria-label="关闭全部 Clash 连接" className="rounded-xl border border-red-500/40 p-4 space-y-3"><p>确认关闭此 Clash 的全部连接？最近采样为 {data?.total_connections ?? confirmAll.count} 条。</p><div className="flex gap-2"><button className={button} disabled={action.busy} onClick={closeAll}>确认关闭全部</button><button className={button} disabled={action.busy} onClick={() => setConfirmAll(null)}>取消</button></div></div>}
    {loading && <p role="status" className={muted}>正在读取连接…</p>}
    {data && <>
      <dl className="grid gap-3 sm:grid-cols-2"><div className={card}><dt className={muted}>累计下载</dt><dd className="mt-1 text-lg font-semibold">{formatBytes(data.downloadTotal)}</dd></div><div className={card}><dt className={muted}>累计上传</dt><dd className="mt-1 text-lg font-semibold">{formatBytes(data.uploadTotal)}</dd></div></dl>
      {data.connections.length === 0 ? <p className={muted}>当前没有活动连接。</p> : <div className="grid gap-3 xl:grid-cols-2">{data.connections.map(connection => <article key={connection.id} className={card}>
        <div className="flex flex-wrap justify-between gap-2"><strong className="break-all">{connectionTarget(connection)}</strong><button className={button} disabled={action.busy} onClick={() => closeOne(connection.id)}>关闭连接</button></div>
        <p className="mt-2 text-sm">{connection.metadata?.network || '未知网络'} · {connection.metadata?.type || '未知类型'} · 规则：{connection.rule || '未知'}</p>
        <p className="mt-1 text-xs text-[var(--c-500)]">开始：{formatDate(connection.start)} · 链路：{connection.chains?.join(' → ') || '—'}</p>
        <p className="mt-1 text-xs text-[var(--c-500)]">下载 {formatBytes(connection.download)} · 上传 {formatBytes(connection.upload)}</p>
        {connection.metadata && <p className="mt-1 break-all text-xs text-[var(--c-500)]">{connection.metadata.sourceIP}:{connection.metadata.sourcePort} → {connection.metadata.destinationIP}:{connection.metadata.destinationPort}</p>}
      </article>)}</div>}
    </>}
  </div>;
}

function providerUsage(provider: ClashProvider): string | null {
  const info = provider.subscriptionInfo;
  if (!info) return null;
  return `已用 ${formatBytes(numeric(info.Upload) + numeric(info.Download))} / ${formatBytes(numeric(info.Total))} · 到期 ${numeric(info.Expire) ? formatDate(numeric(info.Expire)) : '未知'}`;
}

function ProvidersPanel() {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => clashApi.providers(signal), []), 10000);
  const action = useServiceAction();
  const providers = Object.entries(data?.providers || {});
  const refresh = (name: string) => void action.run(async () => { await clashApi.refreshProvider(name); await refetch(); });
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">代理提供商</h3><p className={muted}>提供商数据按需刷新，不会在客户端保存订阅地址或密码。</p></div><button className={button} disabled={loading || action.busy} onClick={() => void refetch()}>刷新列表</button></div>
    <ServiceMessage error={action.error || error?.message} />
    {loading && <p role="status" className={muted}>正在读取提供商…</p>}
    {!loading && data && providers.length === 0 && <p className={muted}>当前没有代理提供商。</p>}
    <div className="grid gap-4 lg:grid-cols-2">{providers.map(([key, provider]) => <article className={card} key={key}>
      <div className="flex flex-wrap justify-between gap-2"><strong>{provider.name || key}</strong><span className={muted}>{provider.type} · {provider.vehicleType}</span></div>
      {provider.updatedAt && <p className="mt-2 text-xs text-[var(--c-500)]">更新：{formatDate(provider.updatedAt)}</p>}
      {providerUsage(provider) && <p className="mt-2 text-sm">{providerUsage(provider)}</p>}
      <p className="mt-2 text-sm text-[var(--c-400)]">代理节点：{provider.proxies?.length ?? 0}</p>
      <button className={`${button} mt-3`} disabled={action.busy} onClick={() => refresh(key)}>刷新此提供商</button>
    </article>)}</div>
  </div>;
}

function ProfilesPanel({ managed, onManagedChange }: { managed: ClashManagedStatus | null; onManagedChange: () => Promise<unknown> }) {
  const { data, loading, error, refetch } = usePolling(useCallback((signal: AbortSignal) => clashApi.profiles(signal), []), 5000);
  const action = useServiceAction();
  const fileInput = useRef<HTMLInputElement>(null);
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [deleting, setDeleting] = useState<ClashProfile | null>(null);
  const [fileError, setFileError] = useState('');
  const profiles = data || [];
  const save = () => void action.run(async () => {
    const cleanName = name.trim();
    if (!cleanName) throw new Error('请填写配置名称');
    if (!content.trim()) throw new Error('请粘贴或导入 YAML 内容');
    await clashApi.createProfile({ name: cleanName, content });
    setName(''); setContent(''); setFileError('');
    if (fileInput.current) fileInput.current.value = '';
    await refetch();
  });
  const remove = () => void action.run(async () => { if (!deleting) return; await clashApi.deleteProfile(deleting.id); setDeleting(null); await refetch(); });
  const start = (profile: ClashProfile) => void action.run(async () => { await clashApi.startManaged(profile.id); await Promise.all([refetch(), onManagedChange()]); });
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">受管 Clash 配置</h3><p className={muted}>配置文件由 R-Link 独立管理并上传到 API 服务器；启动和停止只作用于受管 Clash 内核。</p></div><button className={button} disabled={loading || action.busy} onClick={() => void refetch()}>刷新配置</button></div>
    <ServiceMessage error={action.error || error?.message || fileError} />
    <form className={`${card} space-y-3`} onSubmit={event => { event.preventDefault(); save(); }}>
      <h4 className="font-semibold">导入 YAML 配置</h4>
      <div className="grid gap-3 md:grid-cols-2"><ServiceField label="配置名称" required maxLength={100} value={name} disabled={action.busy} onChange={event => setName(event.target.value)} /><label className="text-sm">从文件导入<input ref={fileInput} aria-label="选择 Clash YAML 文件" className={`${serviceInput} file:mr-3 file:rounded file:border-0 file:bg-[var(--c-700)] file:px-2 file:py-1`} type="file" accept=".yaml,.yml,text/yaml,text/plain" disabled={action.busy} onChange={event => { const file = event.target.files?.[0]; if (!file) return; void (async () => { setFileError(''); if (file.size > 2 * 1024 * 1024) { setFileError('YAML 文件不能超过 2 MiB'); return; } setName(file.name.replace(/\.(ya?ml|txt)$/i, '')); setContent(await file.text()); })(); }} /></label></div>
      <label className="block text-sm">YAML 内容<textarea aria-label="Clash YAML 内容" required rows={9} maxLength={2 * 1024 * 1024} className={`${serviceInput} font-mono`} value={content} disabled={action.busy} onChange={event => setContent(event.target.value)} placeholder="mixed-port: 7890\nmode: rule" /></label>
      <button className={button} disabled={action.busy}>上传配置</button>
    </form>
    {loading && <p role="status" className={muted}>正在读取受管配置…</p>}
    {!loading && profiles.length === 0 && <p className={muted}>还没有受管配置；可以从上方粘贴或导入 YAML。</p>}
    <div className="grid gap-3 lg:grid-cols-2">{profiles.map(profile => <article className={card} key={profile.id}>
      <div className="flex flex-wrap justify-between gap-2"><strong>{profile.name}</strong><span>{profile.active ? '当前配置' : '未使用'}</span></div>
      <p className="mt-2 text-xs text-[var(--c-500)]">更新：{formatDate(profile.updated_at)}</p>
      <div className="mt-3 flex flex-wrap gap-2"><button className={button} disabled={action.busy || !managed?.available || managed.state === 'running'} onClick={() => start(profile)}>启动受管内核</button><button className={button} disabled={action.busy || profile.active || managed?.state === 'running'} onClick={() => setDeleting(profile)}>删除</button></div>
    </article>)}</div>
    {deleting && <div role="dialog" aria-label="删除受管配置" className="rounded-xl border border-red-500/40 p-4 space-y-3"><p>确认删除配置“{deleting.name}”？正在使用中的配置不能删除。</p><div className="flex gap-2"><button className={button} disabled={action.busy} onClick={remove}>确认删除</button><button className={button} disabled={action.busy} onClick={() => setDeleting(null)}>取消</button></div></div>}
  </div>;
}

function StatusCard({ status, loading, error, onRefresh, onStop, busy, actionError, onProfiles }: { status: ClashStatus | null; loading: boolean; error: Error | null; onRefresh: () => Promise<void>; onStop: () => void; busy: boolean; actionError: string; onProfiles: () => void }) {
  const state = connectionState(status, loading, error);
  const managed = status?.managed;
  return <div className={card}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">连接状态</h3><p className={muted}>连接状态来自 API 服务器实际探测结果。</p></div><div className="flex flex-wrap gap-2"><span role="status" className={`rounded-full border px-3 py-1 text-sm ${status?.connected ? 'border-emerald-500/50 text-emerald-400' : 'border-[var(--c-700)] text-[var(--c-400)]'}`}>{state}</span><button className={button} disabled={loading} onClick={() => void onRefresh()}>刷新状态</button></div></div>
    {error && <p role="alert" className="mt-3 text-red-400">{error.message}</p>}
    {actionError && <p role="alert" className="mt-3 text-red-400">{actionError}</p>}
    {status?.error && <p role="alert" className="mt-3 text-red-400">{status.error}</p>}
    {status && <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-[var(--c-500)]">API 服务器</dt><dd className="break-all font-mono">{status.controller_url || '未设置'}</dd></div><div><dt className="text-[var(--c-500)]">Clash 版本</dt><dd>{status.version || '未提供'}</dd></div></dl>}
    {managed && <div className="mt-4 border-t border-[var(--c-800)] pt-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><strong>受管内核</strong><p className={muted}>{managed.available ? `状态：${managed.state}${managed.pid ? ` · PID ${managed.pid}` : ''}` : '当前环境不可用'}</p></div><div className="flex gap-2">{managed.available && managed.state === 'running' && <button className={button} disabled={busy} onClick={onStop}>停止受管内核</button>}{managed.available && managed.state !== 'running' && <button className={button} disabled={busy} onClick={onProfiles}>{managed.profile_id ? '管理受管配置' : '选择受管配置'}</button>}</div></div>{managed.error && <p className="mt-2 text-red-400 text-sm">{managed.error}</p>}</div>}
  </div>;
}

export function ClashView() {
  const [tab, setTab] = useState<ClashTab>('overview');
  const [controllerUrl, setControllerUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [clearSecret, setClearSecret] = useState(false);
  const { data: status, loading: statusLoading, error: statusError, refetch: refetchStatus } = usePolling(useCallback((signal: AbortSignal) => clashApi.status(signal), []), 5000);
  const { data: settings, loading: settingsLoading, error: settingsError, refetch: refetchSettings } = usePolling(useCallback((signal: AbortSignal) => clashApi.settings(signal), []));
  const action = useServiceAction();
  const managedAction = useServiceAction();

  useEffect(() => {
    if (!settings) return;
    setControllerUrl(settings.controller_url);
    setSecret('');
    setClearSecret(false);
  }, [settings]);

  const saveSettings = () => void action.run(async () => {
    const input: { controller_url: string; secret?: string; clear_secret?: boolean } = { controller_url: controllerUrl.trim() };
    if (secret.trim()) input.secret = secret;
    if (clearSecret) input.clear_secret = true;
    await clashApi.saveSettings(input);
    setSecret('');
    setClearSecret(false);
    await Promise.all([refetchSettings(), refetchStatus()]);
  });
  const stopManaged = () => void managedAction.run(async () => { await clashApi.stopManaged(); await refetchStatus(); });
  const gotoProfiles = () => setTab('profiles');
  const statusForPanels = status || null;

  return <section className="space-y-5 pb-8">
    <div><h2 className="text-xl font-bold">Clash 代理</h2><p className={muted}>通过 API 服务器控制远端 Clash。这里不会自动接管本机系统代理或 TUN。</p></div>
    <form className={`${card} space-y-4`} onSubmit={event => { event.preventDefault(); saveSettings(); }}>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">控制器连接</h3><p className={muted}>目标是 API 服务器主机上的 Clash 控制器地址，不是浏览器所在设备的 localhost。</p></div><span className="text-sm text-[var(--c-400)]">{settings?.has_secret ? '已保存密码' : '未保存密码'}</span></div>
      <ServiceMessage error={action.error || settingsError?.message} />
      <fieldset disabled={action.busy || settingsLoading} className="grid gap-3 md:grid-cols-2"><ServiceField label="控制器 URL" required type="url" maxLength={2048} value={controllerUrl} onChange={event => setControllerUrl(event.target.value)} placeholder="http://127.0.0.1:9090" /><ServiceField label="控制器密码（留空保持不变）" type="password" autoComplete="new-password" value={secret} onChange={event => { setSecret(event.target.value); if (event.target.value) setClearSecret(false); }} placeholder={settings?.has_secret ? '已保存，留空保持不变' : '可选'} /></fieldset>
      <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={clearSecret} disabled={action.busy || settingsLoading || Boolean(secret)} onChange={event => setClearSecret(event.target.checked)} />清除服务端已保存密码</label>
      <div className="flex flex-wrap items-center gap-3"><button className={button} disabled={action.busy || settingsLoading}>保存并连接</button><span className="text-xs text-[var(--c-500)]">控制器密码仅保存在服务端，本页面不会长期保存密码。</span></div>
    </form>
    <StatusCard status={statusForPanels} loading={statusLoading} error={statusError} onRefresh={refetchStatus} onStop={stopManaged} busy={managedAction.busy} actionError={managedAction.error} onProfiles={gotoProfiles} />
    <div role="tablist" aria-label="Clash 管理面板" className="flex gap-2 overflow-x-auto border-b border-[var(--c-800)] pb-2">
      {tabs.map(item => <button key={item.id} role="tab" aria-selected={tab === item.id} aria-controls={`clash-panel-${item.id}`} className={`${button} whitespace-nowrap ${tab === item.id ? 'bg-[var(--c-800)] text-[var(--c-100)]' : 'text-[var(--c-400)]'}`} onClick={() => setTab(item.id)}>{item.label}</button>)}
    </div>
    <div id={`clash-panel-${tab}`} role="tabpanel" tabIndex={0}>
      {tab === 'overview' && status?.connected && <ConfigPanel key={`config-${status.controller_url}-${status.version || ''}`} status={status} />}
      {tab === 'overview' && status && !status.connected && <div className={card}><h3 className="font-semibold">代理运行配置</h3><div className="mt-3"><ConnectedGate status={status} /></div></div>}
      {tab === 'proxies' && <>{status?.connected ? <ProxiesPanel key={`proxies-${status.controller_url}-${status.version || ''}`} /> : <div className={card}><ConnectedGate status={statusForPanels} /></div>}</>}
      {tab === 'rules' && <>{status?.connected ? <RulesPanel key={`rules-${status.controller_url}-${status.version || ''}`} /> : <div className={card}><ConnectedGate status={statusForPanels} /></div>}</>}
      {tab === 'connections' && <>{status?.connected ? <ConnectionsPanel key={`connections-${status.controller_url}-${status.version || ''}`} /> : <div className={card}><ConnectedGate status={statusForPanels} /></div>}</>}
      {tab === 'providers' && <>{status?.connected ? <ProvidersPanel key={`providers-${status.controller_url}-${status.version || ''}`} /> : <div className={card}><ConnectedGate status={statusForPanels} /></div>}</>}
      {tab === 'profiles' && <ProfilesPanel managed={status?.managed || null} onManagedChange={refetchStatus} />}
    </div>
  </section>;
}

export default ClashView;
