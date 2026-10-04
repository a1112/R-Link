import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { devicesApi, type Device, type DeviceInput, type DeviceManagementStatus, type DeviceOnboarding, type DevicePlatform, type DeviceSyncResult, type DeviceType } from '../../api/devices';
import { probeDevices } from '../../api/device-batch';
import { saveBlob } from '../../utils/download';
import { connectionLabels, deviceAccessMode, devicePlatforms, deviceTypes, deviceWebUrl, officialInstallUrl, sourceLabels } from '../device-presentation';

const empty: DeviceInput = { name: '', host: '', port: 22, username: '', device_type: 'other', platform: 'unknown', tags: [], notes: '', access_mode: 'ssh', web_scheme: 'https', gateway_id: null };
const inputStyle = 'w-full min-w-0 rounded border border-[var(--c-700)] bg-[var(--c-950)] p-2';
const buttonStyle = 'rounded border px-3 py-2 disabled:opacity-50';
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export type DeviceInitialAction = { kind: 'add' } | { kind: 'edit'; deviceId: string };
export function RemoteView({ onSsh, initialAction, onInitialActionHandled }: { onSsh?: (device: Device) => void; initialAction?: DeviceInitialAction | null; onInitialActionHandled?: () => void }) {
  const handledInitialAction = useRef<DeviceInitialAction | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [management, setManagement] = useState<DeviceManagementStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState<DeviceInput | null>(null);
  const [tagInput, setTagInput] = useState('');
  const [editing, setEditing] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<string>();
  const [revoking, setRevoking] = useState<string>();
  const [linking, setLinking] = useState<string>();
  const [peerId, setPeerId] = useState('');
  const [onboarding, setOnboarding] = useState<DeviceOnboarding | null>(null);
  const [conflicts, setConflicts] = useState<DeviceSyncResult['conflicts']>([]);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [platformFilter, setPlatformFilter] = useState('all');
  const [tagFilter, setTagFilter] = useState('all');
  const [notice, setNotice] = useState('');
  const [batch, setBatch] = useState<{ completed: number; total: number } | null>(null);
  const batchController = useRef<AbortController | null>(null);
  const importInput = useRef<HTMLInputElement>(null);
  const [pendingImport, setPendingImport] = useState<{ name: string; data: unknown; count: number } | null>(null);
  const mounted = useRef(false);
  const generation = useRef(0);
  const mutation = useRef(false);
  const request = useRef<AbortController | null>(null);
  const operationController = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const poll = useRef<() => void>(() => {});
  const current = (signal: AbortSignal, token = generation.current) => mounted.current && !signal.aborted && token === generation.current;

  const refresh = useCallback(async (signal: AbortSignal, token: number) => {
    try {
      const [inventory, info] = await Promise.all([devicesApi.list(signal), devicesApi.managementStatus(signal)]);
      if (!mounted.current || signal.aborted || token !== generation.current) return;
      setDevices(inventory); setManagement(info); setLoading(false); setError('');
    } catch (failure) {
      if (!mounted.current || signal.aborted || token !== generation.current) return;
      // A failed snapshot must not leave yesterday's online result on screen.
      setDevices([]); setManagement(null); setLoading(false); setError(message(failure));
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    generation.current++;
    poll.current = () => {
      if (!mounted.current || mutation.current) return;
      const controller = new AbortController(); request.current = controller;
      const token = generation.current;
      void refresh(controller.signal, token).finally(() => {
        // Only the current, uncancelled snapshot owns the next poll. A late
        // aborted request cannot start a second chain after a mutation ends.
        if (mounted.current && !mutation.current && !controller.signal.aborted && token === generation.current && request.current === controller) {
          clearTimeout(timer.current);
          timer.current = setTimeout(poll.current, 5000);
        }
      });
    };
    poll.current();
    return () => {
      mounted.current = false; generation.current++; clearTimeout(timer.current);
      request.current?.abort(); operationController.current?.abort(); batchController.current?.abort();
    };
  }, [refresh]);
  const perform = async (operation: (signal: AbortSignal, active: () => boolean) => Promise<void>) => {
    // A ref closes the gap before React renders disabled controls.
    if (mutation.current || !mounted.current) return;
    mutation.current = true; generation.current++; clearTimeout(timer.current); request.current?.abort();
    request.current = null;
    const controller = new AbortController(); operationController.current = controller;
    const token = generation.current;
    const active = () => current(controller.signal, token);
    setBusy(true); setError(''); setNotice('');
    try { await operation(controller.signal, active); }
    catch (failure) { if (active()) setError(message(failure)); }
    finally {
      if (active()) { setBusy(false); mutation.current = false; timer.current = setTimeout(poll.current, 5000); }
    }
  };
  const filtered = useMemo(() => devices.filter(device =>
    (status === 'all' || device.status === status) &&
    (typeFilter === 'all' || (device.device_type ?? 'other') === typeFilter) &&
    (platformFilter === 'all' || (device.platform ?? 'unknown') === platformFilter) &&
    (tagFilter === 'all' || device.tags?.includes(tagFilter)) &&
    `${device.name} ${device.host} ${device.username} ${(device.tags ?? []).join(' ')} ${(device.mesh_groups ?? []).map(group => group.name).join(' ')}`.toLowerCase().includes(search.trim().toLowerCase())), [devices, search, status, typeFilter, platformFilter, tagFilter]);
  const tags = [...new Set(devices.flatMap(device => device.tags ?? []))].sort();
  const gateways = devices.filter(device => device.source === 'netbird' && device.connection_status !== 'revoked' && device.id !== editing);
  const unavailableGatewayId = form?.gateway_id && !gateways.some(device => device.id === form.gateway_id) ? form.gateway_id : null;
  const unavailableGateway = devices.find(device => device.id === unavailableGatewayId);
  const editingPeer = devices.find(device => device.id === editing)?.source === 'netbird';
  const updateDevice = (saved: Device) => setDevices(previous => [...previous.filter(item => item.id !== saved.id), saved]);
  const edit = useCallback((device?: Device) => {
    setEditing(device?.id);
    setForm(device ? { name: device.name, host: device.host, port: device.port, username: device.username, device_type: device.device_type ?? 'other', platform: device.platform ?? 'unknown', tags: device.tags ?? [], notes: device.notes ?? '', access_mode: device.access_mode ?? (device.source === 'netbird' ? 'none' : 'ssh'), web_scheme: device.web_scheme ?? 'https', gateway_id: device.gateway_id ?? null } : { ...empty, tags: [] });
    setTagInput((device?.tags ?? []).join(', '));
  }, []);
  useEffect(() => {
    if (!initialAction || initialAction === handledInitialAction.current || loading || busy || error) return;
    handledInitialAction.current = initialAction;
    if (initialAction.kind === 'add') edit();
    else {
      const target = devices.find(device => device.id === initialAction.deviceId);
      if (target) edit(target);
      else setNotice('所选设备已不在当前清单中，请刷新后重试。');
    }
    onInitialActionHandled?.();
  }, [initialAction, loading, busy, error, devices, edit, onInitialActionHandled]);

  return <div className="h-full min-w-0 overflow-auto space-y-5 pb-6">
    <div className="flex flex-wrap justify-between gap-3">
      <div><h2 className="text-xl font-bold">设备管理</h2><p className="text-sm text-[var(--c-400)]">统一登记与同步组网设备。组网状态、网关状态和指定 TCP 端口检测分别显示。</p></div>
      <div className="flex flex-wrap gap-2">
        <button disabled={busy} onClick={() => void perform(signal => refresh(signal, generation.current))} className={buttonStyle}>刷新列表</button>
        <button disabled={busy || loading} onClick={() => edit()} className={buttonStyle}>添加设备</button>
        <button disabled={busy || loading || !management?.configured || management.syncing} className={buttonStyle} onClick={() => void perform(async (signal, active) => {
          setConflicts([]);
          try {
            const result = await devicesApi.sync(signal);
            if (!active()) return;
            setConflicts(result.conflicts);
            setNotice(`同步完成：新增 ${result.added} 台，更新 ${result.updated} 台，缺失 ${result.missing} 台，冲突 ${result.conflicts.length} 项。`);
            await refresh(signal, generation.current);
          } catch (failure) {
            if (!active()) return;
            setDevices(previous => previous.map(device => ({ ...device, connection_status: 'unknown', gateway_status: device.source === 'gateway' ? 'unknown' : null })));
            await refresh(signal, generation.current);
            throw failure;
          }
        })}>{management?.syncing ? '服务端正在同步…' : '同步组网设备'}</button>
        <button disabled={busy} className={buttonStyle} onClick={() => void perform(async (signal, active) => { const guide = await devicesApi.onboarding(signal); if (active()) setOnboarding(guide); })}>设备接入指引</button>
      </div>
    </div>
    {management && <div className="text-sm text-[var(--c-400)] space-y-1">
      {!management.configured && <p>服务端尚未配置 NetBird，请配置管理地址和访问令牌后接入设备。</p>}
      {management.last_synced_at && <p>上次组网同步：{new Date(management.last_synced_at).toLocaleString()} · 超过 {management.stale_seconds} 秒未更新时状态视为未知。</p>}
      {management.last_error && <p className="text-amber-400">组网同步异常：{management.last_error}</p>}
    </div>}
    {onboarding && <section aria-label="设备接入指引" className="rounded-xl border border-[var(--c-700)] p-4 space-y-3 text-sm">
      <div className="flex justify-between gap-3"><h3 className="font-semibold">设备接入指引</h3><button onClick={() => setOnboarding(null)}>关闭指引</button></div>
      {onboarding.management_url && <p className="break-all">组网管理地址：{onboarding.management_url}</p>}
      <ol className="list-decimal pl-5 space-y-2">{onboarding.instructions.map((step, index) => <li key={index}>{step}</li>)}</ol>
      <div className="flex flex-wrap gap-4">{onboarding.platforms.map(platform => officialInstallUrl(platform.url) && <a key={platform.id} href={officialInstallUrl(platform.url)!} className="underline" target="_blank" rel="noreferrer">{platform.name}</a>)}</div>
    </section>}
    <div className="flex flex-wrap gap-3 items-center text-sm">
      <input aria-label="搜索设备" placeholder="搜索名称、地址、用户名、标签或组名" className={`${inputStyle} flex-1 basis-56`} value={search} disabled={busy} onChange={e => setSearch(e.target.value)} />
      <select aria-label="检测状态筛选" value={status} disabled={busy} onChange={e => setStatus(e.target.value)} className={`${inputStyle} w-auto`}>
        <option value="all">全部检测状态</option><option value="reachable">端口可达</option><option value="unreachable">端口不可达</option><option value="unchecked">未检测</option>
      </select>
      <select aria-label="设备类型筛选" value={typeFilter} disabled={busy} onChange={e => setTypeFilter(e.target.value)} className={`${inputStyle} w-auto`}><option value="all">全部设备类型</option>{Object.entries(deviceTypes).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select>
      <select aria-label="平台筛选" value={platformFilter} disabled={busy} onChange={e => setPlatformFilter(e.target.value)} className={`${inputStyle} w-auto`}><option value="all">全部平台</option>{Object.entries(devicePlatforms).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select>
      <select aria-label="标签筛选" value={tagFilter} disabled={busy} onChange={e => setTagFilter(e.target.value)} className={`${inputStyle} w-auto`}><option value="all">全部标签</option>{tags.map(tag => <option key={tag} value={tag}>{tag}</option>)}</select>
      <button disabled={busy || loading || !filtered.length} className={buttonStyle} onClick={() => void perform(async (signal, active) => {
        const targets = [...filtered]; const controller = new AbortController(); batchController.current = controller;
        const abort = () => controller.abort(); signal.addEventListener('abort', abort, { once: true });
        setBatch({ completed: 0, total: targets.length });
        try {
          const result = await probeDevices(targets, controller.signal,
            checked => { if (active()) setDevices(previous => previous.map(item => item.id === checked.id ? checked : item)); },
            completed => { if (active()) setBatch({ completed, total: targets.length }); });
          if (!active()) return;
          setNotice(`${result.cancelled ? '已停止后续检测' : '批量检测结束'}：完成 ${result.completed}/${targets.length}`);
          if (result.errors.length) setError(result.errors.join('；'));
        } finally { signal.removeEventListener('abort', abort); if (active()) setBatch(null); batchController.current = null; }
      })}>检测筛选结果 ({filtered.length})</button>
      <button disabled={busy || loading} className={buttonStyle} onClick={() => void perform(async (signal, active) => {
        const inventory = await devicesApi.export(2, signal); if (!active()) return;
        saveBlob(new Blob([JSON.stringify(inventory, null, 2)], { type: 'application/json' }), 'r-link-devices.json');
        setNotice('设备清单已导出，不含密码、私钥、组网身份或旧检测结果。');
      })}>导出清单</button>
      <button disabled={busy || loading} className={buttonStyle} onClick={() => importInput.current?.click()}>导入清单</button>
      <input className="hidden" ref={importInput} type="file" accept=".json,application/json" aria-label="选择设备清单" disabled={busy || loading} onChange={event => {
        const file = event.target.files?.[0]; event.target.value = ''; if (!file) return;
        void perform(async (_signal, active) => {
          if (file.size > 1024 * 1024) throw new Error('设备清单不能超过 1 MiB');
          const data: unknown = JSON.parse(await file.text());
          if (!data || typeof data !== 'object' || !('version' in data) || ![1, 2].includes(Number(data.version)) || !('devices' in data) || !Array.isArray(data.devices) || data.devices.length > 256) throw new Error('请选择有效的设备清单 JSON，最多 256 台设备');
          if (active()) setPendingImport({ name: file.name, data, count: data.devices.length });
        });
      }} />
    </div>
    {batch && <div role="status" className="text-sm">正在检测 {batch.completed}/{batch.total}（最多同时 4 台）<button className="ml-4 underline" onClick={() => batchController.current?.abort()}>停止检测</button></div>}
    {notice && <p role="status" className="text-emerald-400 text-sm">{notice}</p>}
    {conflicts.length > 0 && <ul className="text-sm text-amber-400 space-y-1">{conflicts.map(conflict => <li key={conflict.peer_id} className="break-all">节点 {conflict.peer_id}：{conflict.host}:{conflict.port} 已被记录 {conflict.device_id} 占用，请检查后明确关联。</li>)}</ul>}
    {pendingImport && <div role="dialog" aria-label="导入设备清单" className="rounded border border-[var(--c-700)] p-4 space-y-3">
      <p className="break-all">{pendingImport.name}：{pendingImport.count} 台设备。重复的主机及端口将跳过；现有设备不会被覆盖。组网身份及网关关联需重新确认。</p>
      <button disabled={busy} className={`${buttonStyle} mr-4`} onClick={() => void perform(async (signal, active) => {
        const result = await devicesApi.import(pendingImport.data, signal); if (!active()) return;
        setPendingImport(null); setNotice(`导入完成：新增 ${result.added} 台，跳过 ${result.skipped} 台。`);
        await refresh(signal, generation.current);
      })}>确认导入</button><button disabled={busy} onClick={() => setPendingImport(null)}>取消导入</button>
    </div>}
    {error && <p role="alert" className="text-red-400 break-words">{error}</p>}
    {loading && <p>正在读取设备…</p>}
    {!loading && devices.length === 0 && !error && <p className="text-[var(--c-400)]">尚未登记设备。添加主机名或 IP 地址后可检测连通性，或同步已入网节点。</p>}
    {form && <form className="p-4 rounded-xl border border-[var(--c-700)] space-y-3" onSubmit={event => {
      event.preventDefault();
      void perform(async (signal, active) => {
        const normalizedTags = [...new Set(tagInput.split(/[,，]/).map(tag => tag.trim()).filter(Boolean))];
        if (normalizedTags.length > 16 || normalizedTags.some(tag => tag.length > 32)) throw new Error('最多 16 个标签，每个标签最多 32 个字符');
        const saved = await devicesApi.save({ ...form, tags: normalizedTags }, editing, signal);
        if (active()) { updateDevice(saved); setForm(null); }
      });
    }}>
      <h3>{editing ? '编辑设备' : '添加设备'}</h3>
      <fieldset disabled={busy} className="grid md:grid-cols-2 gap-3 min-w-0">
        <label>设备名称<input className={inputStyle} required maxLength={80} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
        <label>主机名或 IP<input aria-label="主机名或 IP" className={inputStyle} required maxLength={253} disabled={editingPeer} value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} />{editingPeer && <span className="text-xs text-[var(--c-400)]">地址由组网服务同步。</span>}</label>
        <label>TCP / 服务端口<input className={inputStyle} required type="number" min={1} max={65535} value={form.port} onChange={e => setForm({ ...form, port: Number(e.target.value) })} /></label>
        <label>SSH 用户名（可选）<input className={inputStyle} maxLength={80} value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></label>
        <label>设备类型<select className={inputStyle} value={form.device_type} onChange={e => setForm({ ...form, device_type: e.target.value as DeviceType })}>{Object.entries(deviceTypes).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label>操作系统<select className={inputStyle} value={form.platform} onChange={e => setForm({ ...form, platform: e.target.value as DevicePlatform })}>{Object.entries(devicePlatforms).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label>标签（逗号分隔）<input className={inputStyle} maxLength={550} value={tagInput} onChange={e => setTagInput(e.target.value)} /></label>
        <label>访问方式<select className={inputStyle} value={form.access_mode} onChange={e => setForm({ ...form, access_mode: e.target.value as DeviceInput['access_mode'] })}><option value="ssh">SSH</option><option value="web">Web 服务</option><option value="none">仅管理设备</option></select></label>
        {form.access_mode === 'web' && <label>Web 协议<select className={inputStyle} value={form.web_scheme} onChange={e => setForm({ ...form, web_scheme: e.target.value as 'http' | 'https' })}><option value="https">HTTPS</option><option value="http">HTTP</option></select></label>}
        <label>接入网关<select className={inputStyle} disabled={editingPeer} value={form.gateway_id ?? ''} onChange={e => setForm({ ...form, gateway_id: e.target.value || null })}><option value="">不关联网关</option>{unavailableGatewayId && <option value={unavailableGatewayId} disabled>当前网关：{unavailableGateway?.name ?? unavailableGatewayId} · {unavailableGateway?.connection_status === 'revoked' ? '已撤销（不可用）' : '不可用'}</option>}{gateways.map(device => <option key={device.id} value={device.id}>{device.name} · {connectionLabels[device.connection_status ?? 'unknown']}</option>)}</select></label>
        <label className="md:col-span-2">备注<textarea className={inputStyle} maxLength={500} rows={3} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></label>
      </fieldset>
      <p className="text-xs text-[var(--c-400)]">网关关联用于登记接入关系；路由及访问策略需在组网服务中配置。网关在线不代表子设备健康。连接时再提供密码或私钥。</p>
      <button disabled={busy} type="submit" className={`${buttonStyle} mr-3`}>保存设备</button><button disabled={busy} type="button" onClick={() => setForm(null)}>取消</button>
    </form>}
    {!loading && devices.length > 0 && filtered.length === 0 && <p>没有符合筛选条件的设备。</p>}
    <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{filtered.map(device => <article key={device.id} className="min-w-0 rounded-xl p-4 border border-[var(--c-800)] bg-[var(--c-900)] space-y-3">
      <h3 className="font-semibold break-words">{device.name}</h3>
      <p className="font-mono text-sm break-all">{device.host.includes(':') ? `[${device.host}]` : device.host}:{device.port}</p>
      <p className="text-xs text-[var(--c-400)]">{deviceTypes[device.device_type ?? 'other']} · {devicePlatforms[device.platform ?? 'unknown']} · {sourceLabels[device.source ?? 'manual']}</p>
      <p className={device.connection_status === 'online' ? 'text-emerald-400' : 'text-[var(--c-400)]'}>组网状态：{connectionLabels[device.connection_status ?? 'unknown']}</p>
      {device.source === 'gateway' && <div className="text-sm"><p>网关状态：{connectionLabels[device.gateway_status ?? 'unknown']}</p><p className="text-xs text-[var(--c-400)]">网关在线不代表此设备在线或服务正常。</p></div>}
      {device.peer_id && <p className="text-xs break-all text-[var(--c-400)]">组网 peer ID：{device.peer_id}</p>}
      {(device.mesh_groups?.length ?? 0) > 0 && <p className="text-xs break-words">组网分组：{device.mesh_groups!.map(group => group.name).join('、')}</p>}
      {(device.tags?.length ?? 0) > 0 && <p className="text-xs break-words">标签：{device.tags!.join('、')}</p>}
      {device.notes && <p className="text-sm whitespace-pre-wrap break-words">{device.notes}</p>}
      {device.last_seen && <p className="text-xs text-[var(--c-400)]">节点最后出现：{new Date(device.last_seen).toLocaleString()}</p>}
      <p className={device.status === 'reachable' ? 'text-emerald-400' : 'text-[var(--c-400)]'}>{device.status === 'unchecked' ? '尚未检测' : device.status === 'reachable' ? `上次检测：端口可达${device.latency_ms !== null ? ` · ${device.latency_ms} ms` : ''}` : '上次检测：端口不可达'}</p>
      {device.checked_at && <p className="text-xs text-[var(--c-400)]">检测时间：{new Date(device.checked_at).toLocaleString()} · 仅代表当时的 TCP 端口结果。</p>}
      <div className="flex flex-wrap gap-3 text-sm">
        <button disabled={busy} onClick={() => void perform(async (signal, active) => { const checked = await devicesApi.probe(device.id, signal); if (active()) updateDevice(checked); })}>检测端口</button>
        {onSsh && deviceAccessMode(device) === 'ssh' && <button disabled={busy} onClick={() => onSsh(device)}>SSH 连接</button>}
        {!busy && deviceWebUrl(device) && <a href={deviceWebUrl(device)!} target="_blank" rel="noreferrer">打开 Web 服务</a>}
        <button disabled={busy} onClick={() => edit(device)}>编辑</button>
        {device.source !== 'netbird' && !device.gateway_id && <button disabled={busy || !management?.configured} onClick={() => { setLinking(device.id); setPeerId(''); }}>关联组网节点</button>}
        {device.source === 'netbird' && device.peer_id && device.connection_status !== 'revoked' && <button disabled={busy || !management?.configured} onClick={() => setRevoking(device.id)}>撤销入网</button>}
        <button disabled={busy} onClick={() => setDeleting(device.id)}>删除</button>
      </div>
      {device.gateway_id && <p className="text-xs text-[var(--c-400)]">如需直接关联组网节点，请先解除网关关联。</p>}
      {linking === device.id && device.source !== 'netbird' && !device.gateway_id && <form className="text-sm space-y-2" onSubmit={event => { event.preventDefault(); void perform(async (signal, active) => {
        if (!/^[A-Za-z0-9_-]{1,80}$/.test(peerId.trim())) throw new Error('peer ID 只能包含字母、数字、下划线及短横线，最多 80 个字符');
        const linked = await devicesApi.link(device.id, peerId.trim(), signal); if (active()) { updateDevice(linked); setLinking(undefined); setNotice('已关联指定组网节点。'); }
      }); }}><p>请输入已入网节点的 peer ID。明确关联会保留本地名称与标签，不按 IP 自动合并。</p><label>组网 peer ID<input className={inputStyle} required maxLength={80} value={peerId} disabled={busy} onChange={event => setPeerId(event.target.value)} /></label><button disabled={busy} type="submit" className="mr-3">确认关联</button><button type="button" disabled={busy} onClick={() => setLinking(undefined)}>取消关联</button></form>}
      {revoking === device.id && <div className="text-sm space-y-2"><p>确认撤销此设备的真实组网身份？设备将失去组网接入，清单记录保留为已撤销。</p><button className="mr-3" disabled={busy} onClick={() => void perform(async (signal, active) => {
        const revoked = await devicesApi.revoke(device.id, signal); if (!active()) return;
        updateDevice(revoked); setRevoking(undefined); setNotice('已撤销入网，清单记录已保留。'); await refresh(signal, generation.current);
      })}>确认撤销入网</button><button disabled={busy} onClick={() => setRevoking(undefined)}>取消撤销</button></div>}
      {deleting === device.id && <div className="text-sm space-y-2"><p>删除清单记录不会撤销入网。组网节点将不再自动恢复到清单；关联此网关的子设备会改为手工登记。</p><button className="mr-3" disabled={busy} onClick={() => void perform(async (signal, active) => {
        await devicesApi.remove(device.id, signal); if (!active()) return;
        setDevices(previous => previous.filter(item => item.id !== device.id)); setDeleting(undefined); await refresh(signal, generation.current);
      })}>确认删除</button><button disabled={busy} onClick={() => setDeleting(undefined)}>取消删除</button></div>}
    </article>)}</div>
  </div>;
}
export default RemoteView;
