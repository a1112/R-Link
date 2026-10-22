import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { devicesApi, type Device } from '../api/devices';
import {
  cloneQoSConfig,
  createQoSPolicy,
  isLiteralUnicastIp,
  normalizeQoSConfig,
  qosApi,
  validateQoSConfig,
  type QoSPolicy,
  type QoSConfig,
  type QoSState,
  type QoSStatus,
} from '../api/qos';
import { serviceButton as button, serviceInput, ServiceMessage } from './common/ServiceControls';

const card = 'rounded-xl border border-[var(--c-800)] bg-[var(--c-900)] p-4';
const muted = 'text-sm text-[var(--c-400)]';

type PendingDisable = { revision: number; cleanup: boolean };
type PendingAction = PendingDisable | null;
type PendingApply = { revision: number; config: QoSConfig };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isConflict(error: unknown): boolean {
  return /(?:\b409\b|conflict|版本)/i.test(errorMessage(error));
}

function isBadGateway(error: unknown): boolean {
  return /\b502\b|bad gateway/i.test(errorMessage(error));
}

function cleanupRevision(status: QoSStatus): number | null {
  return status.applied?.revision ?? status.cleanup_revision ?? null;
}

function isCleanupOnly(status: QoSStatus): boolean {
  return status.applied === null && status.cleanup_revision != null;
}

function stateLabel(state: QoSState): string {
  switch (state) {
    case 'active': return '已应用';
    case 'pending': return '已保存，等待应用';
    case 'error': return '应用失败';
    case 'unavailable': return '当前环境不可用';
    default: return '尚未应用';
  }
}

function numberOrNull(value: string): number | null {
  if (value.trim() === '') return null;
  return Number(value);
}

function makePolicyId(index: number): string {
  return `policy-${Date.now().toString(36)}-${index}`.slice(0, 64);
}

function deviceLabel(device: Device): string {
  const address = isLiteralUnicastIp(device.host) ? device.host : `${device.host}（需填写 IP）`;
  return `${device.name} · ${address}`;
}

function sourceSummary(policy: QoSPolicy): string {
  const status = policy.enabled ? '' : ' · 已停用';
  return `${policy.label || policy.id}（${policy.ip || '未填写 IP'}${status}）`;
}

function sameQoSConfig(left: QoSConfig, right: QoSConfig): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function QosManager() {
  const mounted = useRef(false);
  const statusGeneration = useRef(0);
  const statusController = useRef<AbortController | null>(null);
  const mutationGeneration = useRef(0);
  const busyRef = useRef(false);
  const dirtyRef = useRef(false);
  const pendingApplyRef = useRef<PendingApply | null>(null);
  const pendingActionRef = useRef<PendingDisable | null>(null);
  const conflictRefreshRef = useRef(false);

  const [status, setStatus] = useState<QoSStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState('');
  const [draft, setDraft] = useState<QoSConfig | null>(null);
  const [draftRevision, setDraftRevision] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [devices, setDevices] = useState<Device[]>([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [devicesError, setDevicesError] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [pendingApply, setPendingApply] = useState<PendingApply | null>(null);
  const [pendingRemoveId, setPendingRemoveId] = useState<string | null>(null);
  const [conflictNeedsRebase, setConflictNeedsRebase] = useState(false);
  const [conflictRefreshReady, setConflictRefreshReady] = useState(false);

  const adoptStatus = useCallback((next: QoSStatus, forceDraft = false) => {
    if (conflictRefreshRef.current) {
      conflictRefreshRef.current = false;
      setConflictRefreshReady(true);
    }
    const openApply = pendingApplyRef.current;
    if (openApply && (next.desired.revision !== openApply.revision || !sameQoSConfig(next.desired.config, openApply.config))) {
      pendingApplyRef.current = null;
      setPendingApply(null);
      setActionError('服务端保存策略已变化，原应用确认已取消，请检查并重新确认。');
    }
    const openDisable = pendingActionRef.current;
    if (openDisable && (cleanupRevision(next) !== openDisable.revision || isCleanupOnly(next) !== openDisable.cleanup)) {
      pendingActionRef.current = null;
      setPendingAction(null);
      setActionError('服务端清理记录已变化，原停用确认已取消，请重新检查并确认。');
    }
    setStatus(next);
    if (forceDraft || !dirtyRef.current) {
      dirtyRef.current = false;
      setDirty(false);
      setDraft(cloneQoSConfig(next.desired.config));
      setDraftRevision(next.desired.revision);
    }
  }, []);

  const loadStatus = useCallback(async (force = false) => {
    if (busyRef.current && !force) return;
    const generation = ++statusGeneration.current;
    statusController.current?.abort();
    const controller = new AbortController();
    statusController.current = controller;
    setStatusLoading(true);
    try {
      const next = await qosApi.status(controller.signal);
      if (!mounted.current || generation !== statusGeneration.current) return;
      setStatusError('');
      adoptStatus(next);
    } catch (error) {
      if (!mounted.current || generation !== statusGeneration.current || controller.signal.aborted) return;
      setStatusError(errorMessage(error));
    } finally {
      if (mounted.current && generation === statusGeneration.current) setStatusLoading(false);
    }
  }, [adoptStatus]);

  useEffect(() => {
    mounted.current = true;
    void loadStatus();
    const timer = window.setInterval(() => { void loadStatus(); }, 5000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      statusController.current?.abort();
    };
  }, [loadStatus]);

  useEffect(() => {
    const controller = new AbortController();
    setDevicesLoading(true);
    void devicesApi.list(controller.signal).then(next => {
      if (!mounted.current || controller.signal.aborted) return;
      setDevices(next);
      setDevicesError('');
    }).catch(error => {
      if (!mounted.current || controller.signal.aborted) return;
      setDevicesError(errorMessage(error));
    }).finally(() => {
      if (mounted.current && !controller.signal.aborted) setDevicesLoading(false);
    });
    return () => controller.abort();
  }, []);

  const updateDraft = useCallback((updater: (current: QoSConfig) => QoSConfig) => {
    if (!draft) return;
    if (!dirtyRef.current) {
      dirtyRef.current = true;
      setDirty(true);
      setDraftRevision(status?.desired.revision ?? draftRevision);
    }
    setDraft(current => current ? updater(current) : current);
    setActionError('');
    setActionMessage('');
  }, [draft, draftRevision, status]);

  const updatePolicy = useCallback((id: string, updater: (policy: QoSPolicy) => QoSPolicy) => {
    updateDraft(current => ({
      ...current,
      policies: current.policies.map(policy => policy.id === id ? updater(policy) : policy),
    }));
  }, [updateDraft]);

  const beginMutation = useCallback((): number | null => {
    if (busyRef.current) return null;
    statusGeneration.current += 1;
    statusController.current?.abort();
    statusController.current = null;
    setStatusLoading(false);
    busyRef.current = true;
    const generation = ++mutationGeneration.current;
    setBusy(true);
    setActionError('');
    setActionMessage('');
    return generation;
  }, []);

  const endMutation = useCallback((generation: number) => {
    if (!mounted.current || generation !== mutationGeneration.current) return;
    busyRef.current = false;
    setBusy(false);
  }, []);

  const isCurrentMutation = useCallback((generation: number) => mounted.current && generation === mutationGeneration.current, []);

  const saveConfig = useCallback(async () => {
    if (!draft) return;
    if (conflictNeedsRebase) {
      setActionError('请先选择以最新保存版本为基础继续保存，或放弃草稿载入最新配置。');
      return;
    }
    const normalized = normalizeQoSConfig(draft);
    const validationError = validateQoSConfig(normalized);
    if (validationError) {
      setActionError(validationError);
      return;
    }
    if (draftRevision === null) {
      setActionError('策略版本尚未读取，请先刷新状态。');
      return;
    }
    const generation = beginMutation();
    if (generation === null) return;
    let refreshAfterMutation = false;
    try {
      const next = await qosApi.saveConfig(draftRevision, normalized);
      if (!isCurrentMutation(generation)) return;
      adoptStatus(next, true);
      setConflictNeedsRebase(false);
      setConflictRefreshReady(false);
      setActionMessage('策略已保存；网络状态未改变。');
    } catch (error) {
      if (!isCurrentMutation(generation)) return;
      if (isConflict(error)) {
        refreshAfterMutation = true;
        conflictRefreshRef.current = true;
        setConflictRefreshReady(false);
        setConflictNeedsRebase(true);
        setActionError('策略版本已变化（409），当前草稿已保留。刷新后可选择“以最新保存版本为基础继续保存”；这会覆盖服务端最新保存策略，但不会立即修改网络，也可以放弃修改载入最新配置。');
      } else {
        setActionError(`保存策略失败：${errorMessage(error)}`);
      }
    } finally {
      endMutation(generation);
      if (refreshAfterMutation) void loadStatus(true);
    }
  }, [adoptStatus, beginMutation, conflictNeedsRebase, draft, draftRevision, endMutation, isCurrentMutation, loadStatus]);

  const rebaseDraft = useCallback(() => {
    if (!status || !dirtyRef.current || !conflictRefreshReady) {
      setActionError('请先成功刷新服务端策略版本，再选择继续保存。');
      return;
    }
    setDraftRevision(status.desired.revision);
    setConflictNeedsRebase(false);
    setActionError('');
    setActionMessage('已选择以最新保存版本为基础继续保存；下一次保存会覆盖服务端最新保存策略，但不会立即修改网络。');
  }, [conflictRefreshReady, status]);

  const applyConfig = useCallback(async (confirmed: PendingApply | null) => {
    if (!status || !draft || !confirmed) return;
    if (dirtyRef.current) {
      setActionError('确认后配置又发生了未保存修改，请重新确认应用。');
      setPendingApply(null);
      return;
    }
    if (status.desired.revision !== confirmed.revision || draftRevision !== confirmed.revision || !sameQoSConfig(status.desired.config, confirmed.config) || !sameQoSConfig(draft, confirmed.config)) {
      setActionError('服务端或当前策略已变化，原确认已失效，请重新检查并确认应用。');
      setPendingApply(null);
      return;
    }
    if (!status.capabilities.available) {
      setActionError('当前环境不能应用 QoS；策略仍可以保存。');
      setPendingApply(null);
      return;
    }
    if (!draft.interface.trim()) {
      setActionError('应用前请选择网络接口。');
      setPendingApply(null);
      return;
    }
    if (draftRevision === null) {
      setActionError('策略版本尚未读取，请先刷新状态。');
      setPendingApply(null);
      return;
    }
    const generation = beginMutation();
    if (generation === null) return;
    let refreshAfterMutation = false;
    try {
      const next = await qosApi.apply(confirmed.revision);
      if (!isCurrentMutation(generation)) return;
      adoptStatus(next, true);
      setActionMessage('策略已提交到服务端。');
    } catch (error) {
      if (!isCurrentMutation(generation)) return;
      if (isConflict(error)) {
        refreshAfterMutation = true;
        setActionError('策略版本已变化（409），请刷新状态后重新确认应用。');
      } else {
        setActionError(`应用策略失败：${errorMessage(error)}`);
      }
    } finally {
      endMutation(generation);
      if (refreshAfterMutation) void loadStatus(true);
    }
  }, [adoptStatus, beginMutation, draft, draftRevision, endMutation, isCurrentMutation, loadStatus, status]);

  const disableApplied = useCallback(async (confirmed: PendingDisable | null) => {
    if (!status || !confirmed || cleanupRevision(status) !== confirmed.revision || isCleanupOnly(status) !== confirmed.cleanup) {
      setActionError('服务端清理记录已变化，原停用确认已失效，请刷新状态后重新确认。');
      return;
    }
    if (dirtyRef.current) {
      setActionError('当前有未保存修改，请先保存或放弃修改，再停用已应用限速。');
      pendingActionRef.current = null;
      setPendingAction(null);
      return;
    }
    const generation = beginMutation();
    if (generation === null) return;
    let refreshAfterFailure = false;
    try {
      const next = await qosApi.removeApplied(confirmed.revision);
      if (!isCurrentMutation(generation)) return;
      adoptStatus(next, true);
      if (next.applied === null && next.cleanup_revision == null && (next.state === 'inactive' || next.state === 'pending') && !next.error) {
        setActionMessage('已停用服务端限速，保存的策略记录仍保留。');
      } else {
        setActionError('服务端尚未确认限速已停用，请检查清理状态后再试。');
      }
    } catch (error) {
      if (!isCurrentMutation(generation)) return;
      if (isConflict(error)) {
        refreshAfterFailure = true;
        setActionError('状态版本已变化（409），请刷新状态后再试。');
      } else {
        refreshAfterFailure = isBadGateway(error);
        setActionError(`停用限速失败：${errorMessage(error)}`);
      }
    } finally {
      endMutation(generation);
      if (refreshAfterFailure) void loadStatus(true);
    }
  }, [adoptStatus, beginMutation, endMutation, isCurrentMutation, loadStatus, status]);

  const discardDraft = () => {
    if (!status) return;
    dirtyRef.current = false;
    setDirty(false);
    setDraft(cloneQoSConfig(status.desired.config));
    setDraftRevision(status.desired.revision);
    pendingActionRef.current = null;
    setPendingAction(null);
    pendingApplyRef.current = null;
    setPendingApply(null);
    setPendingRemoveId(null);
    setConflictNeedsRebase(false);
    conflictRefreshRef.current = false;
    setConflictRefreshReady(false);
    setActionError('');
    setActionMessage('已放弃未保存修改。');
  };

  const interfaceOptions = useMemo(() => {
    if (!draft) return [];
    return [...new Set([draft.interface, ...(status?.capabilities.interfaces || []).map(item => item.name)])].filter(Boolean);
  }, [draft, status]);

  const deviceById = useMemo(() => new Map(devices.map(device => [device.id, device])), [devices]);

  if (statusLoading && !status) {
    return <section className={`${card} space-y-2`} aria-label="设备 QoS 策略"><h3 className="font-semibold">设备 QoS 策略</h3><p role="status" className={muted}>正在读取 QoS 状态…</p></section>;
  }

  if (!status || !draft) {
    return <section className={`${card} space-y-2`} aria-label="设备 QoS 策略"><h3 className="font-semibold">设备 QoS 策略</h3><p className="text-red-400">{statusError || '暂时无法读取 QoS 状态。'}</p><button className={button} disabled={statusLoading || busy || pendingAction !== null || pendingApply !== null} onClick={() => void loadStatus()}>刷新 QoS 状态</button></section>;
  }

  const capability = status.capabilities;
  const appliedRevision = status.applied?.revision ?? null;
  const cleanupRevisionValue = status.cleanup_revision ?? null;
  const cleanupOnly = isCleanupOnly(status);
  const disableRevision = appliedRevision ?? cleanupRevisionValue;
  const appliedVerified = status.applied !== null && status.state === 'active' && !status.error;
  const appliedRevisionLabel = appliedRevision !== null
    ? appliedVerified ? `#${appliedRevision}（已核验）` : `#${appliedRevision}（记录，未核验）`
    : cleanupRevisionValue !== null ? `#${cleanupRevisionValue}（清理未完成，未核验）` : '尚无应用记录';
  const policyCount = draft.policies.length;
  const confirmationOpen = pendingAction !== null || pendingApply !== null;
  const applyDisabled = busy || confirmationOpen || !capability.available;
  const devicePolicyCount = draft.policies.length;

  return <section className="space-y-4" aria-label="设备 QoS 策略">
    <div className={`${card} space-y-3`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="font-semibold">设备 QoS 策略</h3><p className={`mt-1 ${muted}`}>为设备设置上传和下载带宽上限、保障带宽与优先级。</p></div>
        <span className={`rounded-full px-2 py-1 text-xs ${capability.available ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>{capability.available ? 'QoS 可用' : '当前环境不可用'}</span>
      </div>
      {!capability.available && <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-sm text-amber-200"><p>{capability.reason || '当前服务端没有可用的 QoS 执行环境。'}</p><p className="mt-1">可以保存策略草稿，但不会改变网络。应用需要 Linux、root 或 CAP_NET_ADMIN 权限、tc/HTB/IFB 以及作为网关的网络接口。</p></div>}
      {capability.available && <p className={muted}>方向以设备为准：上传是设备发往网络，下载是网络发往设备。</p>}
      <div className="grid gap-3 sm:grid-cols-3">
        <div><span className={muted}>策略状态</span><p className="mt-1 font-medium">{stateLabel(status.state)}</p></div>
        <div><span className={muted}>已保存版本</span><p className="mt-1 font-medium">#{status.desired.revision}</p></div>
        <div><span className={muted}>应用记录版本</span><p className="mt-1 font-medium">{appliedRevisionLabel}</p></div>
      </div>
      {status.error && <p className="text-red-400">{status.error}</p>}
      {statusError && <p className="text-red-400">状态刷新失败：{statusError}</p>}
      <div className="flex flex-wrap gap-2">
        <button className={button} disabled={statusLoading || busy || confirmationOpen} onClick={() => void loadStatus()}>刷新 QoS 状态</button>
        {dirty && <button className={button} disabled={busy} onClick={discardDraft}>放弃未保存修改</button>}
      </div>
    </div>

    <div className={`${card} space-y-4`}>
      <fieldset disabled={busy} className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold">保存的策略</h4><p className={muted}>{dirty ? '有未保存修改。状态刷新不会覆盖当前编辑。' : '当前编辑内容与已保存策略一致。'}</p></div><span className={dirty ? 'text-sm text-amber-300' : 'text-sm text-emerald-300'}>{dirty ? '草稿未保存' : '已保存'}</span></div>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">服务端接口<select className={serviceInput} aria-label="QoS 服务端接口" value={draft.interface} onChange={event => updateDraft(current => ({ ...current, interface: event.target.value }))}><option value="">请选择接口</option>{interfaceOptions.map(name => <option key={name} value={name}>{name}</option>)}</select></label>
        <label className="text-sm">接口总上传上限（Mbps）<input className={serviceInput} aria-label="接口总上传上限" type="number" min={1} max={100000} step="0.1" value={draft.upload_mbps} onChange={event => updateDraft(current => ({ ...current, upload_mbps: Number(event.target.value) }))} /></label>
        <label className="text-sm">接口总下载上限（Mbps）<input className={serviceInput} aria-label="接口总下载上限" type="number" min={1} max={100000} step="0.1" value={draft.download_mbps} onChange={event => updateDraft(current => ({ ...current, download_mbps: Number(event.target.value) }))} /></label>
      </div>
      <p className={muted}>接口总量覆盖该接口看到的全部流量，也包括未匹配设备策略的流量；空白的设备上限表示使用共享总量。</p>
      </fieldset>
    </div>

    <div className={`${card} space-y-4`}>
      <fieldset disabled={busy} className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold">设备策略（{policyCount}/64）</h4><p className={muted}>设备名称仅用于辅助填写，规则始终使用你确认的 IP 地址。</p></div><button className={button} disabled={busy || policyCount >= 64} onClick={() => updateDraft(current => ({ ...current, policies: [...current.policies, createQoSPolicy(makePolicyId(current.policies.length), `设备 ${current.policies.length + 1}`)] }))}>添加设备策略</button></div>
      {devicesError && <p className="text-sm text-amber-300">设备清单读取失败：{devicesError}。仍可手动输入 IP。</p>}
      {devicesLoading && <p role="status" className={muted}>正在读取设备清单…</p>}
      {policyCount === 0 && <p className={`${muted} rounded-lg border border-[var(--c-800)] p-4`}>还没有设备策略，可以手动添加。</p>}
      <div className="space-y-4">{draft.policies.map((policy, index) => {
        const selectedDevice = policy.device_id ? deviceById.get(policy.device_id) : undefined;
        const selectedDeviceIsHostname = Boolean(selectedDevice && !isLiteralUnicastIp(selectedDevice.host));
        return <div key={policy.id} className="rounded-lg border border-[var(--c-800)] p-4 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h5 className="font-medium">设备策略 {index + 1}</h5><p className={muted}>策略移除只会修改草稿，保存后才会更新服务端策略。</p></div><div className="flex items-center gap-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label={`启用策略 ${index + 1}`} checked={policy.enabled} onChange={event => updatePolicy(policy.id, current => ({ ...current, enabled: event.target.checked }))} />启用</label>{pendingRemoveId === policy.id ? <span className="flex gap-2"><button className={button} disabled={busy} onClick={() => { updateDraft(current => ({ ...current, policies: current.policies.filter(item => item.id !== policy.id) })); setPendingRemoveId(null); }}>确认移除</button><button className={button} disabled={busy} onClick={() => setPendingRemoveId(null)}>取消</button></span> : <button className={button} disabled={busy} onClick={() => setPendingRemoveId(policy.id)}>移除</button>}</div></div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm">策略名称<input className={serviceInput} aria-label={`策略名称 ${index + 1}`} maxLength={80} value={policy.label} onChange={event => updatePolicy(policy.id, current => ({ ...current, label: event.target.value }))} /></label>
            <label className="text-sm">绑定设备<select className={serviceInput} aria-label={`绑定设备 ${index + 1}`} value={policy.device_id || ''} onChange={event => { const nextDevice = event.target.value ? deviceById.get(event.target.value) : undefined; updatePolicy(policy.id, current => ({ ...current, device_id: nextDevice?.id || null, ip: nextDevice && isLiteralUnicastIp(nextDevice.host) ? nextDevice.host.trim() : '' })); }}><option value="">手动输入来源 IP</option>{policy.device_id && !deviceById.has(policy.device_id) && <option value={policy.device_id}>已保存设备（当前清单不可用）</option>}{devices.map(device => <option key={device.id} value={device.id}>{deviceLabel(device)}</option>)}</select></label>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm">来源 IP（设备侧）<input className={serviceInput} aria-label={`来源 IP ${index + 1}`} inputMode="decimal" value={policy.ip} onChange={event => updatePolicy(policy.id, current => ({ ...current, ip: event.target.value }))} placeholder="例如 192.168.1.20" /></label>
            <label className="text-sm">设备上传上限（Mbps）<input className={serviceInput} aria-label={`设备上传上限 ${index + 1}`} type="number" min={0.001} step="0.1" value={policy.upload_mbps ?? ''} onChange={event => updatePolicy(policy.id, current => ({ ...current, upload_mbps: numberOrNull(event.target.value) }))} placeholder="共享总量" /></label>
            <label className="text-sm">设备下载上限（Mbps）<input className={serviceInput} aria-label={`设备下载上限 ${index + 1}`} type="number" min={0.001} step="0.1" value={policy.download_mbps ?? ''} onChange={event => updatePolicy(policy.id, current => ({ ...current, download_mbps: numberOrNull(event.target.value) }))} placeholder="共享总量" /></label>
          </div>
          {selectedDeviceIsHostname && <p className="text-sm text-amber-300">该设备登记的是主机名，系统不会自动解析；请手动填写设备的字面 IP。</p>}
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm">上传保障（Mbps）<input className={serviceInput} aria-label={`上传保障 ${index + 1}`} type="number" min={0.001} step="0.1" value={policy.guaranteed_upload_mbps} onChange={event => updatePolicy(policy.id, current => ({ ...current, guaranteed_upload_mbps: Number(event.target.value) }))} /></label>
            <label className="text-sm">下载保障（Mbps）<input className={serviceInput} aria-label={`下载保障 ${index + 1}`} type="number" min={0.001} step="0.1" value={policy.guaranteed_download_mbps} onChange={event => updatePolicy(policy.id, current => ({ ...current, guaranteed_download_mbps: Number(event.target.value) }))} /></label>
            <label className="text-sm">优先级<select className={serviceInput} aria-label={`策略优先级 ${index + 1}`} value={policy.priority} onChange={event => updatePolicy(policy.id, current => ({ ...current, priority: Number(event.target.value) as 0 | 3 | 7 }))}><option value={0}>高（0）</option><option value={3}>普通（3）</option><option value={7}>低（7）</option></select></label>
          </div>
        </div>;
      })}</div>
      <p className={muted}>优先级表示满足保障带宽后借用剩余带宽的顺序；它不承诺网络时延。</p>
      </fieldset>
    </div>

    <ServiceMessage error={actionError}>{actionMessage && <p role="status" className="text-emerald-400">{actionMessage}</p>}</ServiceMessage>
    {conflictNeedsRebase && dirty && <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-sm text-amber-200"><p>当前草稿仍在编辑中。成功刷新服务端版本后，你可以明确选择以最新保存版本为基础继续保存；这会覆盖服务端最新保存策略，但不会立即修改网络。</p><div className="mt-2 flex flex-wrap gap-2"><button className={button} disabled={busy || !conflictRefreshReady} onClick={rebaseDraft}>以最新保存版本为基础继续保存</button><button className={button} disabled={busy} onClick={discardDraft}>放弃草稿并载入最新保存策略</button></div></div>}
    <div className={`${card} flex flex-wrap items-center justify-between gap-3`}>
      <div className={muted}>{dirty ? '保存后才能应用当前草稿。' : `当前配置包含 ${devicePolicyCount} 条设备策略。`}</div>
      <div className="flex flex-wrap gap-2">
        <button className={button} disabled={busy || confirmationOpen || !dirty} onClick={() => void saveConfig()}>保存策略</button>
        <button className={button} disabled={applyDisabled} onClick={() => { if (dirtyRef.current) { setActionError('当前有未保存修改，请先保存策略再应用。'); return; } if (!draft.interface.trim()) { setActionError('应用前请选择网络接口。'); return; } if (draftRevision === null) { setActionError('策略版本尚未读取，请先刷新状态。'); return; } const confirmed = { revision: draftRevision, config: cloneQoSConfig(draft) }; pendingApplyRef.current = confirmed; setPendingApply(confirmed); }}>应用到服务端</button>
        {disableRevision !== null && <button className={button} disabled={busy || confirmationOpen} onClick={() => { if (dirtyRef.current) { setActionError('当前有未保存修改，请先保存或放弃修改，再停用已应用限速。'); return; } const pending = { revision: disableRevision, cleanup: cleanupOnly }; pendingActionRef.current = pending; setPendingAction(pending); }}>{cleanupOnly ? '完成未清理限速' : '停用已应用限速'}</button>}
      </div>
    </div>

    {pendingApply && <div role="dialog" aria-modal="true" aria-label="确认应用 QoS 策略" className={`${card} space-y-3 border-amber-500/50`}><div><h4 className="font-semibold">确认应用 QoS 策略</h4><p className={`mt-2 ${muted}`}>将把版本 #{pendingApply.revision} 的配置应用到接口「{pendingApply.config.interface}」：接口总上传 {pendingApply.config.upload_mbps} Mbps、总下载 {pendingApply.config.download_mbps} Mbps，共 {pendingApply.config.policies.length} 条设备策略。</p><ul className="mt-2 max-h-48 overflow-auto list-disc pl-5 text-sm">{pendingApply.config.policies.slice(0, 10).map(policy => <li key={policy.id}>{sourceSummary(policy)}</li>)}{pendingApply.config.policies.length > 10 && <li>其余 {pendingApply.config.policies.length - 10} 条设备策略</li>}</ul></div><div className="flex gap-2"><button className={button} disabled={busy || !capability.available || dirty} onClick={() => { const confirmed = pendingApplyRef.current; pendingApplyRef.current = null; setPendingApply(null); void applyConfig(confirmed); }}>确认应用</button><button className={button} disabled={busy} onClick={() => { pendingApplyRef.current = null; setPendingApply(null); }}>取消</button></div></div>}
    {pendingAction && <div role="dialog" aria-modal="true" aria-label="确认停用 QoS 限速" className={`${card} space-y-3 border-red-500/50`}><div><h4 className="font-semibold">{pendingAction.cleanup ? '确认完成清理未完成限速' : '确认停用已应用限速'}</h4><p className={`mt-2 ${muted}`}>{pendingAction.cleanup ? '服务端记录显示上一次限速清理未完成，将按当前清理记录重试删除。' : '这会删除服务端当前的 QoS 限制。'}将按记录版本 #{pendingAction.revision} 执行，并保留已保存的设备策略记录。</p></div><div className="flex gap-2"><button className={button} disabled={busy} onClick={() => { const confirmed = pendingActionRef.current; pendingActionRef.current = null; setPendingAction(null); void disableApplied(confirmed); }}>{pendingAction.cleanup ? '确认完成清理' : '确认停用'}</button><button className={button} disabled={busy} onClick={() => { pendingActionRef.current = null; setPendingAction(null); }}>取消</button></div></div>}
  </section>;
}

export default QosManager;

