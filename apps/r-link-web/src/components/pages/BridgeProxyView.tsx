import { useCallback, useEffect, useRef, useState } from 'react';
import { bridgeProxyApi as api, BridgeProxyError, object, records, text, type BridgeAdapter, type BridgeTarget, type JsonObject } from '../../api/bridgeproxy';
import { isAccountAdmin } from '../../api/account-access';
import { useAccountState } from '../../hooks/useAccount';
import { isTauriRuntime } from '../../utils/tauriWindow';

const input = 'w-full rounded-lg border border-[var(--c-700)] bg-[var(--c-950)] px-3 py-2 text-sm';
const button = 'rounded-lg border border-[var(--c-700)] px-3 py-2 text-sm hover:bg-[var(--c-800)] disabled:opacity-40 disabled:cursor-not-allowed';
const panel = 'rounded-xl border border-[var(--c-800)] p-4 space-y-4';
const tabs = ['概览', '出口配置', '发现与配对', '链路管理', '分流规则', '流量接管', '连接与流量', '诊断与日志', '节点升级', '核心 API'] as const;
type Tab = typeof tabs[number];
type Draft = { name: string; mixed_port: number; api_port: number; allow_lan: boolean; bypass_lan: boolean; final_action: string; outbound: { kind: string; host: string; port: number; username: string; password: string; udp_over_tcp: boolean; custom_json: string } };
type Rule = { enabled: boolean; kind: string; value: string; action: string };
const initial: Draft = { name: '', mixed_port: 17891, api_port: 17892, allow_lan: false, bypass_lan: true, final_action: 'proxy', outbound: { kind: 'direct', host: '127.0.0.1', port: 7890, username: '', password: '', udp_over_tcp: false, custom_json: '' } };
export function newerVersion(candidate: unknown, current: unknown): boolean {
  if (typeof candidate !== 'string' || typeof current !== 'string' || !/^\d{1,6}\.\d{1,6}\.\d{1,6}$/.test(candidate) || !/^\d{1,6}\.\d{1,6}\.\d{1,6}$/.test(current)) return false;
  const left = candidate.split('.').map(Number), right = current.split('.').map(Number);
  for (let i = 0; i < 3; i++) { if (left[i] !== right[i]) return left[i] > right[i]; }
  return false;
}
function safeDraft(value: JsonObject): Draft {
  const outbound = object(value.outbound);
  return { name: text(value.name, ''), mixed_port: Number(value.mixed_port ?? 17891), api_port: Number(value.api_port ?? 17892), allow_lan: value.allow_lan === true, bypass_lan: value.bypass_lan !== false, final_action: text(value.final_action, 'proxy'),
    outbound: { kind: text(outbound.kind, 'direct'), host: text(outbound.host, ''), port: Number(outbound.port ?? 7890), username: text(outbound.username, ''), password: '', udp_over_tcp: outbound.udp_over_tcp === true, custom_json: '' } };
}
function Details({ value }: { value: unknown }) { return <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-[var(--c-900)] p-3 text-xs">{JSON.stringify(value ?? {}, null, 2)}</pre>; }
function Flag({ label, value }: { label: string; value: unknown }) { return <div className="rounded-lg border border-[var(--c-800)] p-3"><span className="text-xs text-[var(--c-400)]">{label}</span><strong className="mt-1 block text-sm">{value === true ? '已启用' : value === false ? '未启用' : text(value)}</strong></div>; }
function Check({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean }) { return <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={checked} disabled={disabled} onChange={event => onChange(event.target.checked)} />{label}</label>; }

function supportsRoute(manifest: JsonObject, method: string, path: string): boolean {
  return records(manifest.routes).some(route => {
    if (route.method !== method || route.available !== true || typeof route.path !== 'string') return false;
    const expected = route.path.split('/'), actual = path.split('/');
    return expected.length === actual.length && expected.every((part, index) => part === actual[index] || (part === '{id}' && /^[A-Za-z0-9_-]{1,128}$/.test(actual[index])));
  });
}

export default function BridgeProxyView() {
  const account = useAccountState();
  const desktop = isTauriRuntime();
  const [target, setTarget] = useState<BridgeTarget>(desktop ? 'local' : 'server');
  const [adapter, setAdapter] = useState<BridgeAdapter | null>(null);
  const [dataDir, setDataDir] = useState('');
  const [allowControl, setAllowControl] = useState(false);
  const [tab, setTab] = useState<Tab>('概览');
  const [resources, setResources] = useState<JsonObject>({});
  const [manifest, setManifest] = useState<JsonObject>({});
  const [operations, setOperations] = useState<JsonObject[]>([]);
  const [pairings, setPairings] = useState<JsonObject>({});
  const [draft, setDraft] = useState<Draft>(initial);
  const [draftRevision, setDraftRevision] = useState<string | undefined>();
  const [rules, setRules] = useState<Rule[]>([]);
  const [dirty, setDirty] = useState(false);
  const [clearPassword, setClearPassword] = useState(false);
  const [codes, setCodes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [observed, setObserved] = useState('');
  const [stale, setStale] = useState(true);
  const [connectionError, setConnectionError] = useState('');
  const [observationSequence, setObservationSequence] = useState(0);
  const [apiDocument, setApiDocument] = useState<unknown>(null);
  const controller = useRef<AbortController | null>(null);
  const dirtyRef = useRef(false);
  const changedFields = useRef(new Set<string>());
  const accountRevision = useRef(account.revision);
  const source = (path: string) => object(resources[`/v1/${path}`]);
  const configState = source('config');
  const config = object(configState.config);
  const revision = typeof configState.revision === 'string' ? configState.revision : undefined;
  const status = source('status');
  const canControl = adapter?.configured === true && adapter.control_configured && (target === 'local' || account.config?.mode !== 'oidc' || !!isAccountAdmin(account));
  const enabled = !!canControl && !busy && !stale;
  const supported = (method: string, path: string) => supportsRoute(manifest, method, path);
  const platform = text(object(manifest.capabilities).platform, adapter?.platform || '未知平台');
  const featureSupported = (feature: string) => object(manifest.capabilities)[feature] === true;
  const takeoverSupported = (path: string) => featureSupported(path.replace(/-/g, '_')) && supported('PUT', `/v1/${path}`);
  const markDirty = () => { dirtyRef.current = true; setDirty(true); };
  const patch = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    markDirty();
    if (key === 'outbound') {
      for (const [field, item] of Object.entries(value as Draft['outbound'])) if (draft.outbound[field as keyof Draft['outbound']] !== item) changedFields.current.add(`outbound.${field}`);
    } else changedFields.current.add(key);
    setDraft(current => ({ ...current, [key]: value }));
  };

  const refresh = useCallback(async (signal: AbortSignal, keepDraft = true) => {
    const [snapshot, capabilities, history] = await Promise.all([
      api.request<JsonObject>(target, { method: 'GET', path: '/v1/snapshot' }, signal),
      api.request<JsonObject>(target, { method: 'GET', path: '/v1/capabilities' }, signal),
      api.request<JsonObject>(target, { method: 'GET', path: '/v1/operations' }, signal),
    ]);
    if (signal.aborted) return;
    const next = object(snapshot.resources);
    if (typeof snapshot.age_ms !== 'number' || snapshot.age_ms < 0 || snapshot.age_ms > 12000) throw new Error('Core 状态已过期，请检查其运行状态并重新刷新');
    if (typeof snapshot.instance_id !== 'string' || snapshot.instance_id !== object(capabilities.host).instance_id || snapshot.instance_id !== history.instance_id) throw new Error('Core 实例在读取时发生变化，请重新刷新');
    setResources(next); setManifest(capabilities); setOperations(records(history.operations)); setObserved(new Date().toLocaleTimeString()); setObservationSequence(current => current + 1); setStale(false); setConnectionError('');
    if (!keepDraft || !dirtyRef.current) {
      setDraft(safeDraft(object(object(next['/v1/config']).config)));
      setDraftRevision(typeof object(next['/v1/config']).revision === 'string' ? object(next['/v1/config']).revision as string : undefined);
      setRules(records(object(next['/v1/rules']).rules).map(rule => ({ enabled: rule.enabled === true, kind: text(rule.kind, 'domain_suffix'), value: text(rule.value, ''), action: text(rule.action, 'proxy') })));
      dirtyRef.current = false; setDirty(false); setClearPassword(false);
      changedFields.current.clear();
    }
  }, [target]);

  useEffect(() => {
    const request = new AbortController(); controller.current?.abort(); controller.current = request;
    setAdapter(null); setResources({}); setManifest({}); setOperations([]); setPairings({}); setCodes({}); setApiDocument(null); setError(''); setMessage(''); setObserved(''); setDraft(initial); setDraftRevision(undefined); setRules([]); setClearPassword(false); setStale(true); setConnectionError('');
    dirtyRef.current = false; changedFields.current.clear(); setDirty(false); setBusy(true);
    if (accountRevision.current !== account.revision) { accountRevision.current = account.revision; if (desktop) void api.disconnect().catch(() => undefined); }
    void api.adapter(target, request.signal).then(async info => {
      if (request.signal.aborted) return; setAdapter(info); if (info.configured) await refresh(request.signal, false);
    }).catch(reason => { if (!request.signal.aborted) setError(reason instanceof Error ? reason.message : 'Core 接入不可用'); })
      .finally(() => { if (!request.signal.aborted) setBusy(false); });
    return () => { request.abort(); controller.current?.abort(); };
  }, [target, account.revision, desktop, refresh]);

  useEffect(() => {
    setPairings({}); setCodes({});
  }, [tab, target, canControl]);

  useEffect(() => {
    if (tab !== '发现与配对' || !canControl) return;
    const request = new AbortController();
    void api.request<JsonObject>(target, { method: 'GET', path: '/v1/pairings/control' }, request.signal)
      .then(value => { if (!request.signal.aborted) setPairings(value); }).catch(reason => { if (!request.signal.aborted) setError(reason instanceof Error ? reason.message : '配对状态不可用'); });
    return () => request.abort();
  }, [tab, target, canControl, observationSequence]);

  useEffect(() => {
    if (!adapter?.configured || busy) return;
    let alive = true;
    const request = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { await refresh(request.signal, true); }
      catch (reason) { if (alive && !request.signal.aborted) { setStale(true); setConnectionError(reason instanceof Error ? reason.message : 'Core 状态暂不可读取'); } }
      if (alive) timer = setTimeout(() => { void poll(); }, 3000);
    };
    timer = setTimeout(() => { void poll(); }, 3000);
    return () => { alive = false; clearTimeout(timer); request.abort(); };
  }, [adapter?.configured, busy, refresh]);

  async function run(action: (signal: AbortSignal) => Promise<unknown>, save = false) {
    controller.current?.abort(); const request = new AbortController(); controller.current = request;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await action(request.signal);
      if (request.signal.aborted) return;
      setMessage(object(result).valid === true ? '配置预检通过，尚未保存或应用。' : '操作已提交，请核对实际运行状态。');
      if (save) { dirtyRef.current = false; setDirty(false); setDraft(current => ({ ...current, outbound: { ...current.outbound, password: '', custom_json: '' } })); }
      await refresh(request.signal, !save);
    } catch (reason) { if (!request.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { if (!request.signal.aborted) setBusy(false); }
  }
  const command = (method: string, path: string, body?: unknown, needsRevision = false, save = false, baseRevision = revision) => run(signal => {
    if (!supported(method, path)) throw new BridgeProxyError('当前 Core 未开放此操作，请核对平台能力清单。', 'unsupported_capability', 501);
    return api.command(target, { method, path, body, ...(needsRevision ? { revision: baseRevision } : {}) }, signal);
  }, save);
  const configPayload = () => {
    const payload: JsonObject = {}, outbound: JsonObject = {};
    for (const field of changedFields.current) {
      if (field.startsWith('outbound.')) {
        const key = field.slice(9) as keyof Draft['outbound'];
        if (key !== 'password' && key !== 'custom_json') outbound[key] = draft.outbound[key];
      } else payload[field] = draft[field as keyof Draft];
    }
    if (draft.outbound.password || clearPassword) outbound.password = clearPassword ? '' : draft.outbound.password;
    if (draft.outbound.custom_json.trim()) outbound.custom_json = draft.outbound.custom_json;
    if (Object.keys(outbound).length) payload.outbound = outbound;
    return payload;
  };
  const maskedChanges = JSON.stringify(configPayload()).includes('[REDACTED]');
  const reload = () => { if (dirty && !window.confirm('刷新会放弃本页未保存的配置和规则，继续？')) return; void run(async signal => { await refresh(signal, false); return {}; }); };

  return <section className="space-y-5 pb-8 text-[var(--c-100)]">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-2xl font-semibold">网络出口与代理</h2><p className="mt-1 text-sm text-[var(--c-400)]">BridgeProxy Core 提供代理、反向隧道和流量接管，独立客户端与 R-Link 共用核心。</p></div><button className={button} disabled={busy || !adapter?.configured} onClick={reload}>刷新状态</button></div>
    <div className={`${panel} bg-[var(--c-900)]`}>
      <div className="flex flex-wrap items-center gap-3"><label className="text-sm">管理目标 <select aria-label="管理目标" className={`${input} mt-1 w-auto`} value={target} disabled={busy} onChange={event => { if (dirty && !window.confirm('切换目标会放弃未保存的修改，继续？')) return; setTarget(event.target.value as BridgeTarget); }}>
        {desktop && <option value="local">这台电脑的 Core</option>}<option value="server">服务端所在机器的 Core</option></select></label><span className="text-xs text-[var(--c-400)]">{adapter?.configured ? stale ? '已配置 · 状态未核验' : adapter.control_configured ? '已连接 · 控制已授权' : '已连接 · 只读' : '尚未连接'}{adapter?.configured && ` · ${platform}`}{observed && ` · 采样 ${observed}`}</span></div>
      {target === 'local' ? <form className="space-y-3" onSubmit={event => { event.preventDefault(); if (dirty && !window.confirm('重新连接会放弃本页未保存的修改，继续？')) return; setAdapter(null); setResources({}); setManifest({}); setOperations([]); setPairings({}); setCodes({}); setDraft(initial); setDraftRevision(undefined); setRules([]); setClearPassword(false); setApiDocument(null); setObserved(''); setStale(true); changedFields.current.clear(); dirtyRef.current = false; setDirty(false); controller.current?.abort(); const request = new AbortController(); controller.current = request; setBusy(true); setError(''); void api.connect(dataDir.trim(), allowControl, request.signal).then(async info => { if (request.signal.aborted) return; setAdapter(info); await refresh(request.signal, false); }).catch(reason => { if (!request.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason)); }).finally(() => { if (!request.signal.aborted) setBusy(false); }); }}>
        <label className="block text-sm">Core 数据目录<input aria-label="Core 数据目录" className={`${input} mt-1`} placeholder={adapter?.platform === 'windows' ? 'C:\\BridgeProxy\\BridgeProxy-data' : 'Core 数据目录的绝对路径'} value={dataDir} onChange={event => setDataDir(event.target.value)} disabled={busy} required /></label>
        <p className="text-xs text-[var(--c-400)]">先启动 BridgeProxy 或独立 Core 的 API，再选择它的数据目录。使用当前系统账户读取私有凭据，连接授权仅保留在当前 R-Link 进程。Windows 使用 DPAPI；Linux/macOS 要求数据目录和凭据仅本人可访问。</p>
        <Check label="允许 R-Link 控制这台电脑的代理、隧道和流量接管" checked={allowControl} onChange={setAllowControl} disabled={busy} />
        <div className="flex gap-2"><button className={button} disabled={busy || adapter?.supported === false || !dataDir.trim()}>连接本机 Core</button>{adapter?.configured && <button type="button" className={button} disabled={busy} onClick={() => { controller.current?.abort(); void api.disconnect().then(() => { setAdapter(null); setResources({}); setPairings({}); setCodes({}); setManifest({}); setMessage('已断开管理连接，Core 继续独立运行。'); }); }}>断开管理连接</button>}</div>
      </form> : <p className="text-sm text-[var(--c-400)]">此目标是 R-Link 服务端所在机器，由服务端管理员配置 Core 接入凭据。它不会控制当前浏览器所在电脑。</p>}
    </div>
    {(error || connectionError) && <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm">{error || connectionError}</div>}
    {message && <div role="status" className="rounded-lg border border-blue-500/40 p-3 text-sm">{message}</div>}
    {!adapter?.configured && !busy && <p className="text-sm text-[var(--c-400)]">连接 Core 后可在此管理网络出口、链路、配对和分流。未连接不代表代理已停止。</p>}
    {adapter?.configured && <>
      <div role="tablist" aria-label="代理功能" className="flex flex-wrap gap-2">{tabs.map(item => <button key={item} role="tab" aria-selected={tab === item} className={`${button} ${tab === item ? 'border-blue-500 bg-blue-500/15' : ''}`} onClick={() => { if (item !== tab && dirty) { if (!window.confirm('切换页面会放弃未保存的配置和规则，继续？')) return; setDraft(safeDraft(config)); setDraftRevision(revision); setRules(records(source('rules').rules).map(rule => ({ enabled: rule.enabled === true, kind: text(rule.kind, 'domain_suffix'), value: text(rule.value, ''), action: text(rule.action, 'proxy') }))); dirtyRef.current = false; changedFields.current.clear(); setDirty(false); setClearPassword(false); } setTab(item); }}>{item}</button>)}</div>
      {tab === '概览' && <div className="space-y-4"><div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Flag label="代理核心" value={stale ? '状态已过期' : status.running === true ? '运行中' : status.starting === true ? '启动中' : status.running === false ? '已停止' : '未知'} /><Flag label="已认证隧道" value={stale ? null : status.tunnel_connected} /><Flag label="TUN 实际状态" value={!featureSupported('tun') ? '当前平台未提供' : stale ? null : status.tun_active} /><Flag label="系统代理实际状态" value={!featureSupported('system_proxy') ? '当前平台未提供' : stale ? null : status.system_proxy_active} /></div>
        <div className={panel}><p className="text-sm">{text(status.status, '尚无运行状态')}{status.last_error ? ` · ${text(status.last_error)}` : ''}</p><div className="flex flex-wrap gap-2">{[['启动代理', 'start'], ['停止代理', 'stop'], ['重启代理', 'restart']].map(([label, action]) => <button key={action} className={button} disabled={!enabled} onClick={() => { if (action !== 'start' && !window.confirm(`${label}会影响当前连接，继续？`)) return; void command('POST', `/v1/service/${action}`); }}>{label}</button>)}</div><p className="text-xs text-[var(--c-400)]">配置已保存、操作已受理和网络实际可用分别核验。需要真实连接时，请结合链路认证与诊断结果。</p></div><Details value={source('runtime')} /></div>}
      {tab === '出口配置' && <form className={panel} onSubmit={event => { event.preventDefault(); void command('PATCH', '/v1/config', { ...configPayload(), apply: true }, true, true, draftRevision); }}>
        <div className="flex justify-between gap-3"><h3 className="font-semibold">本机出口与代理入口</h3>{dirty && <span className="text-xs text-amber-400">有未保存修改</span>}</div><div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm">节点名称<input className={input} value={draft.name} onChange={event => patch('name', event.target.value)} disabled={!enabled} required maxLength={128} /></label>
          <label className="text-sm">本机出站方式<select className={input} value={draft.outbound.kind} disabled={!enabled} onChange={event => patch('outbound', { ...draft.outbound, kind: event.target.value })}><option value="direct">直接联网</option><option value="http">HTTP 上游</option><option value="socks5">SOCKS5 上游</option><option value="custom">自定义出站 JSON</option></select></label>
          <label className="text-sm">代理入口端口<input type="number" min={1} max={65535} className={input} value={draft.mixed_port} onChange={event => patch('mixed_port', Number(event.target.value))} disabled={!enabled} required /></label><label className="text-sm">核心监控端口<input type="number" min={1} max={65535} className={input} value={draft.api_port} onChange={event => patch('api_port', Number(event.target.value))} disabled={!enabled} required /></label>
          {['http', 'socks5'].includes(draft.outbound.kind) && <><label className="text-sm">上游地址<input className={input} value={draft.outbound.host} onChange={event => patch('outbound', { ...draft.outbound, host: event.target.value })} disabled={!enabled} required /></label><label className="text-sm">上游端口<input type="number" min={1} max={65535} className={input} value={draft.outbound.port} onChange={event => patch('outbound', { ...draft.outbound, port: Number(event.target.value) })} disabled={!enabled} required /></label><label className="text-sm">上游用户名<input className={input} value={draft.outbound.username} onChange={event => patch('outbound', { ...draft.outbound, username: event.target.value })} disabled={!enabled} autoComplete="off" /></label><label className="text-sm">新上游密码<input type="password" className={input} value={draft.outbound.password} onChange={event => patch('outbound', { ...draft.outbound, password: event.target.value })} disabled={!enabled} autoComplete="new-password" placeholder={object(config.outbound).has_password ? '已保存密码；留空保留' : '未设置密码'} /></label><Check label="清除已保存上游密码" checked={clearPassword} disabled={!enabled} onChange={value => { markDirty(); setClearPassword(value); }} /><Check label="上游明确支持 UDP over TCP" checked={draft.outbound.udp_over_tcp} disabled={!enabled} onChange={value => patch('outbound', { ...draft.outbound, udp_over_tcp: value })} /></>}
        </div>{draft.outbound.kind === 'custom' && <label className="block text-sm">自定义出站 JSON<textarea aria-label="自定义出站 JSON" className={`${input} mt-1 h-40 font-mono`} value={draft.outbound.custom_json} onChange={event => patch('outbound', { ...draft.outbound, custom_json: event.target.value })} disabled={!enabled} placeholder={object(config.outbound).custom_configured ? '已保存自定义出站；留空保留，内容不会回显' : '{"type":"direct"}'} /></label>}
        <Check label="允许局域网访问代理入口" checked={draft.allow_lan} onChange={value => patch('allow_lan', value)} disabled={!enabled} /><Check label="私网地址绕行" checked={draft.bypass_lan} onChange={value => patch('bypass_lan', value)} disabled={!enabled} />
        {maskedChanges && <p className="text-sm text-amber-400">修改的字段包含脱敏标记，请重新输入完整值。</p>}<div className="flex gap-2"><button type="button" className={button} disabled={!enabled || !draftRevision || maskedChanges} onClick={() => void command('POST', '/v1/config/validate', configPayload(), true, false, draftRevision)}>预检配置</button><button className={button} disabled={!enabled || !draftRevision || maskedChanges}>保存并应用出口配置</button></div><p className="text-xs text-[var(--c-400)]">应用配置可能重建代理连接。选择已配对的网络出口，请在链路管理中设置当前上游。</p>
      </form>}
      {tab === '发现与配对' && <div className="space-y-4"><div className={panel}><h3 className="font-semibold">在线配对</h3><div className="flex gap-2"><button className={button} disabled={!enabled} onClick={() => void command('POST', '/v1/pairing/window', { open: true })}>允许配对 2 分钟</button><button className={button} disabled={!enabled} onClick={() => void command('POST', '/v1/pairing/window', { open: false })}>关闭配对窗口</button></div><p className="text-sm text-[var(--c-400)]">发现结果是候选节点。双方必须分别核对验证码；配对完成后还需要链路认证成功。</p>
        {records(source('nodes').nodes).map(node => <article key={text(node.node_id)} className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--c-800)] pt-3"><div><strong>{text(node.name)}</strong><p className="text-xs text-[var(--c-400)]">{text(node.node_id)} · {node.pairing_open ? '配对窗口开放' : '配对窗口关闭'}</p></div><div className="flex gap-2"><button className={button} disabled={!enabled || !node.pairing_open} onClick={() => void command('POST', '/v1/pairings/request', { node_id: node.node_id, role: 'provider' })}>向其提供网络</button><button className={button} disabled={!enabled || !node.pairing_open} onClick={() => void command('POST', '/v1/pairings/request', { node_id: node.node_id, role: 'consumer' })}>使用其网络</button></div></article>)}{records(source('nodes').nodes).length === 0 && <p className="text-sm text-[var(--c-400)]">暂无发现响应。</p>}</div>
        {records(pairings.pending).map(pair => <div key={text(pair.id)} className={`${panel} border-amber-500/40`}><h3 className="font-semibold">核对与 {text(pair.peer_name)} 的配对</h3><p>本机验证码：<strong className="select-all font-mono text-2xl tracking-widest">{text(pair.verification_code)}</strong></p><p className="text-sm">方向：{text(pair.local_role)} · 剩余 {text(pair.expires_in_secs)} 秒 · 对端{pair.peer_approved ? '已确认' : '尚未确认'}</p><label className="block text-sm">输入对端屏幕上的 8 位验证码<input aria-label={`对端验证码 ${text(pair.id)}`} className={`${input} mt-1 font-mono`} inputMode="numeric" maxLength={8} value={codes[text(pair.id)] || ''} onChange={event => setCodes(current => ({ ...current, [text(pair.id)]: event.target.value }))} disabled={!enabled || pair.local_approved === true} /></label><div className="flex gap-2"><button className={button} disabled={!enabled || pair.local_approved === true || !/^\d{8}$/.test(codes[text(pair.id)] || '')} onClick={() => void command('POST', `/v1/pairings/${text(pair.id)}/decision`, { approve: true, verification_code: codes[text(pair.id)] })}>验证码一致，确认配对</button><button className={button} disabled={!enabled} onClick={() => void command('POST', `/v1/pairings/${text(pair.id)}/decision`, { approve: false })}>拒绝配对</button></div></div>)}
      </div>}
      {tab === '链路管理' && <div className={panel}><h3 className="font-semibold">当前上游与已配对链路</h3><p className="text-sm text-[var(--c-400)]">当前上游：{config.upstream_link_id ? text(config.upstream_link_id) : '本机出站'}。上游失效不会自动切换到本机出口。</p><button className={button} disabled={!enabled || !revision} onClick={() => void command('PATCH', '/v1/config', { upstream_link_id: null, apply: true }, true)}>使用本机出站</button>
        {records(source('links').links).map(link => { const actual = records(status.links).find(item => item.id === link.id); return <article key={text(link.id)} className="space-y-3 border-t border-[var(--c-800)] pt-4"><div className="flex flex-wrap justify-between gap-2"><div><strong>{text(link.name)}</strong><p className="text-xs text-[var(--c-400)]">{text(link.role)} · {link.enabled ? '已启用' : '已停用'} · {actual?.connected ? '已认证连接' : '尚未认证连接'}</p></div><div className="flex flex-wrap gap-2">{link.role === 'consumer' && <button className={button} disabled={!enabled || !revision || link.enabled !== true} onClick={() => void command('PATCH', '/v1/config', { upstream_link_id: link.id, apply: true }, true)}>设为当前上游</button>}<button className={button} disabled={!enabled || !revision} onClick={() => void command('PATCH', `/v1/links/${text(link.id)}`, { enabled: !link.enabled, apply: true }, true)}>{link.enabled ? '停用' : '启用'}</button><button className={button} disabled={!enabled || !revision} onClick={() => { const name = window.prompt('链路名称', text(link.name, '')); if (name?.trim()) void command('PATCH', `/v1/links/${text(link.id)}`, { name: name.trim() }, true); }}>重命名</button><button className={button} disabled={!enabled || !revision} onClick={() => { if (window.confirm('删除此链路及其可信历史？')) void command('DELETE', `/v1/links/${text(link.id)}`, { apply: true }, true); }}>删除</button></div></div><p className="break-all text-xs text-[var(--c-400)]">{text(actual?.endpoint)} · 路径 {Array.isArray(actual?.route_path) ? actual.route_path.join(' → ') : '尚无已确认路径'}</p></article>; })}{records(source('links').links).length === 0 && <p className="text-sm">暂无已保存链路，请先完成双方配对。</p>}</div>}
      {tab === '分流规则' && <div className={panel}><h3 className="font-semibold">有序分流规则</h3><p className="text-sm text-[var(--c-400)]">按顺序匹配，规则外流量使用最终动作；应用时可能影响现有连接。</p>{rules.some(rule => rule.value.includes('[REDACTED]')) && <p className="text-sm text-amber-400">部分规则内容已脱敏。请重新输入完整内容后保存，避免用脱敏标记覆盖原规则。</p>}<label className="block text-sm">最终动作<select className={input} value={draft.final_action} disabled={!enabled} onChange={event => patch('final_action', event.target.value)}><option value="proxy">代理</option><option value="direct">直连</option><option value="block">阻止</option></select></label>
        {rules.map((rule, index) => <div key={index} className="grid items-center gap-2 md:grid-cols-[auto_1fr_2fr_1fr_auto]"><input aria-label={`启用规则 ${index + 1}`} type="checkbox" checked={rule.enabled} disabled={!enabled} onChange={event => { markDirty(); setRules(current => current.map((item, i) => i === index ? { ...item, enabled: event.target.checked } : item)); }} /><select aria-label={`规则类型 ${index + 1}`} className={input} value={rule.kind} disabled={!enabled} onChange={event => { markDirty(); setRules(current => current.map((item, i) => i === index ? { ...item, kind: event.target.value } : item)); }}>{[['domain_suffix', '域名后缀'], ['domain', '完整域名'], ['domain_keyword', '域名关键词'], ['ip_cidr', 'IP / CIDR'], ['process_name', '进程名']].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><input aria-label={`规则内容 ${index + 1}`} className={input} value={rule.value} disabled={!enabled} onChange={event => { markDirty(); setRules(current => current.map((item, i) => i === index ? { ...item, value: event.target.value } : item)); }} /><select aria-label={`规则动作 ${index + 1}`} className={input} value={rule.action} disabled={!enabled} onChange={event => { markDirty(); setRules(current => current.map((item, i) => i === index ? { ...item, action: event.target.value } : item)); }}><option value="proxy">代理</option><option value="direct">直连</option><option value="block">阻止</option></select><div className="flex gap-1"><button className={button} disabled={!enabled || index === 0} onClick={() => { markDirty(); setRules(current => { const next = [...current]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; }); }}>上移</button><button className={button} disabled={!enabled} onClick={() => { markDirty(); setRules(current => current.filter((_, i) => i !== index)); }}>删除</button></div></div>)}
        <div className="flex flex-wrap gap-2"><button className={button} disabled={!enabled || rules.length >= 512} onClick={() => { markDirty(); setRules(current => [...current, { enabled: true, kind: 'domain_suffix', value: '', action: 'proxy' }]); }}>添加规则</button><button className={button} disabled={!enabled || !revision || rules.some(rule => !rule.value.trim() || rule.value.includes('[REDACTED]'))} onClick={() => void command('PUT', '/v1/rules', { rules, final_action: draft.final_action, apply: true }, true, true, draftRevision)}>保存并应用分流规则</button></div></div>}
      {tab === '流量接管' && <div className="space-y-4">{[['tun', 'TUN', '接管 IP 流量，需要对应平台驱动、权限及本机确认。'], ['system-proxy', '系统代理', '影响遵循系统代理设置的应用。'], ['application-proxy', '后台应用代理兼容', '修改当前用户的持久代理环境变量，相关应用需重新启动；停止服务不会自动恢复。']].map(([path, label, help]) => <div key={path} className={panel}><h3 className="font-semibold">{label}</h3><p className="text-sm text-[var(--c-400)]">{help}</p>{!takeoverSupported(path) && <p role="note" className="text-sm text-amber-400">当前 Core 在 {platform} 未提供此功能。</p>}<Details value={source(path)} /><div className="flex gap-2"><button className={button} disabled={!enabled || !revision || !takeoverSupported(path)} onClick={() => { if (!window.confirm(`确认启用${label}？${help}`)) return; void command('PUT', `/v1/${path}`, { enabled: true, ...(path === 'application-proxy' ? {} : { apply: true }) }, true); }}>启用{label}</button><button className={button} disabled={!enabled || !revision || !takeoverSupported(path)} onClick={() => void command('PUT', `/v1/${path}`, { enabled: false, ...(path === 'application-proxy' ? {} : { apply: true }) }, true)}>{path === 'application-proxy' ? '恢复启用前的环境' : `关闭${label}`}</button>{path === 'system-proxy' && <button className={button} disabled={!enabled || !featureSupported('system_proxy') || !supported('POST', '/v1/system-proxy/restore')} onClick={() => void command('POST', '/v1/system-proxy/restore')}>恢复系统代理备份</button>}</div></div>)}</div>}
      {tab === '连接与流量' && <div className="space-y-4"><Details value={source('traffic')} /><div className={panel}><div className="flex justify-between"><h3 className="font-semibold">实际连接</h3><button className={button} disabled={!enabled} onClick={() => { if (window.confirm('断开当前全部代理连接？')) void command('DELETE', '/v1/connections'); }}>断开全部连接</button></div>{records(source('connections').connections).map(connection => <div key={text(connection.id)} className="flex items-center justify-between gap-3 border-t border-[var(--c-800)] pt-3"><div className="min-w-0"><p className="break-all text-sm">{text(connection.host)} → {text(connection.destination)}</p><p className="text-xs text-[var(--c-400)]">{text(connection.network)} · {text(connection.process)} · {text(connection.rule)}</p></div><button className={button} disabled={!enabled} onClick={() => void command('DELETE', `/v1/connections/${text(connection.id)}`)}>断开</button></div>)}{records(source('connections').connections).length === 0 && <p className="text-sm text-[var(--c-400)]">暂无核心报告的连接。</p>}</div></div>}
      {tab === '诊断与日志' && <div className="space-y-4"><div className={panel}><h3 className="font-semibold">连接诊断</h3><div className="flex flex-wrap gap-2">{['all', 'quick', 'stability', 'udp'].map(profile => <button key={profile} className={button} disabled={!enabled || source('diagnostics').running === true} onClick={() => void command('POST', '/v1/diagnostics/run', { profile })}>{profile === 'all' ? '运行完整诊断' : profile.toUpperCase()}</button>)}<button className={button} disabled={!enabled || source('diagnostics').running !== true} onClick={() => void command('POST', '/v1/diagnostics/cancel', { run_id: source('diagnostics').run_id })}>取消当前诊断</button></div><Details value={source('diagnostics')} /></div><div className={panel}><div className="flex justify-between"><h3 className="font-semibold">脱敏运行日志</h3><button className={button} disabled={!enabled} onClick={() => void command('DELETE', '/v1/logs')}>清除内存日志</button></div><Details value={source('logs').logs} /></div></div>}
      {tab === '节点升级' && <div className={panel}><h3 className="font-semibold">通过已认证节点下载新版</h3><p className="text-sm text-[var(--c-400)]">下载来源、版本与 SHA-256 来自实际已认证链路。下载完成后安装仍需在运行 Core 的本机确认。</p>{records(status.links).filter(link => link.connected === true && link.updates_supported === true && newerVersion(object(link.update_offer).version, object(manifest.core).version)).map(link => { const offer = object(link.update_offer); return <div key={text(link.id)} className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--c-800)] pt-3"><div><strong>{text(link.name)} · {text(offer.version)}</strong><p className="break-all font-mono text-xs">{text(offer.sha256)}</p></div><button className={button} disabled={!enabled || !supported('POST', '/v1/updates/download')} onClick={() => { if (window.confirm(`从可信节点 ${text(link.name)} 下载 ${text(offer.version)}？`)) void command('POST', '/v1/updates/download', { link_id: link.id, sha256: offer.sha256 }); }}>下载此节点新版</button></div>; })}{!supported('POST', '/v1/updates/download') && <p className="text-sm text-[var(--c-400)]">当前 Core 不提供节点更新下载；请使用对应平台的独立发行包更新。</p>}<Details value={source('updates')} /></div>}
      {tab === '核心 API' && <div className="space-y-4"><div className={panel}><h3 className="font-semibold">能力与版本</h3><p className="text-sm text-[var(--c-400)]">此清单由当前 Core 返回。R-Link 通过版本化接口使用能力，独立客户端继续使用同一个 Core。</p><Details value={manifest} /><button className={button} disabled={busy} onClick={() => void run(async signal => { const doc = await api.request(target, { method: 'GET', path: '/v1/openapi.json' }, signal); if (!signal.aborted) setApiDocument(doc); return {}; })}>读取完整 OpenAPI</button>{apiDocument !== null && <Details value={apiDocument} />}</div><div className={panel}><h3 className="font-semibold">最近操作</h3><Details value={operations} /></div><div className={panel}><h3 className="font-semibold">控制凭据轮换</h3><p className="text-sm text-[var(--c-400)]">凭据不会显示到页面。本机连接会在下次请求重新读取受保护凭据；服务端接入需要管理员同步更新其配置。</p>{['read', 'control'].map(scope => <button key={scope} className={`${button} mr-2`} disabled={!enabled || !supported('POST', '/v1/tokens/rotate')} onClick={() => { if (window.confirm(`轮换 ${scope} 凭据会使使用旧凭据的连接失效，继续？`)) void command('POST', '/v1/tokens/rotate', { scope }); }}>轮换 {scope} 凭据</button>)}</div></div>}
      {!canControl && <p className="text-xs text-[var(--c-400)]">当前连接为只读。控制本机 Core 需要连接时明确授权；控制服务端 Core 需要管理员权限及服务端控制凭据。</p>}
    </>}
  </section>;
}
