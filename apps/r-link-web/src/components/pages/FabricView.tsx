import { useCallback, useEffect, useRef, useState } from 'react';
import { fabricApi, getNativeFabricStatus, nativeFabricFresh, type Enrollment, type FabricPeer, type NativeFabricStatus } from '../../api/fabric';
import { getAccountState, isAccountAdmin, serviceBase } from '../../api/account-access';
import { useAccountState } from '../../hooks/useAccount';
import { usePolling } from '../../api/usePolling';

const button = 'rounded border border-[var(--c-700)] px-3 py-2 disabled:opacity-50';
const input = 'w-full rounded border border-[var(--c-700)] bg-[var(--c-950)] px-3 py-2';
const unixTime = (value?: number | null) => value && Number.isFinite(value) ? new Date(value * 1000).toLocaleString() : '未上报';
const pathLabels = { direct: '直连', relay: '中转', none: '未观察', probing: '探测中', offline: '未连接' };
const adminAccess = () => { const account = getAccountState(); return account.status === 'ready' && (account.config?.mode === 'local' || account.config?.mode === 'service' || !!isAccountAdmin(account)); };

function NativeStatus({ value }: { value: NativeFabricStatus | null }) {
  const fresh = nativeFabricFresh(value);
  return <article className="rounded-xl border border-[var(--c-800)] p-4 space-y-2"><h3 className="font-semibold">本机 R-Link Agent</h3>{!value ? <p className="text-sm text-[var(--c-400)]">未读取到本机 Agent；浏览器和旧桌面客户端不提供本机原生状态。</p> : <>
    {value.status_error === 'startup_failed' && <p role="alert" className="text-sm text-red-400">组网服务启动失败，请查看本机安装结果。</p>}
    <p className="text-sm">采样：{value.status_error === 'startup_failed' ? '服务启动失败' : fresh ? '当前状态' : '状态已过期或服务未运行'} · {value.mode === 'vpn' ? 'VPN 模式' : '传输测试模式'} · {value.name || value.device_id || '未登记'}</p>
    <p className="text-sm break-all">控制面：{value.control_url || '未配置'} · {fresh && value.control.connected ? '已连接' : '未确认'}</p>
    <p className="text-sm">系统 TUN：{fresh && value.mode === 'vpn' && value.tun.ready ? `${value.tun.name || '已就绪'} · ${value.tun.ip || '未报告 IP'}` : '未确认就绪'}</p>
    {value.mode === 'transport-test' && <p className="text-sm text-amber-400">当前只测试中转与打洞传输，尚未建立系统虚拟网卡，不能据此访问虚拟 IP。</p>}
    {value.peers.map(peer => <p className="text-xs text-[var(--c-400)]" key={peer.peer_id}>{peer.ip || peer.peer_id} · {fresh ? pathLabels[peer.path] || '未知路径' : '状态待确认'} · RTT {!fresh || peer.rtt_ms == null ? '未测量' : `${peer.rtt_ms.toFixed(1)} ms`} · WireGuard 握手 {value.mode === 'vpn' ? unixTime(peer.last_handshake) : '未启用 VPN'}</p>)}
  </>}</article>;
}

function Peer({ peer }: { peer: FabricPeer }) {
  const recent = !!peer.last_seen && Date.now() / 1000 - peer.last_seen <= 45 && peer.last_seen <= Date.now() / 1000 + 5;
  const control = recent && peer.connected && peer.control_connected;
  const tunnel = control && peer.mode === 'vpn' && peer.tunnel_ready_reported;
  const now = Date.now() / 1000;
  const handshake = peer.paths.some(path => ['direct', 'relay'].includes(path.path) && !!path.reported_at && now - path.reported_at <= 45 && path.reported_at <= now + 5 && !!path.last_handshake && now - path.last_handshake <= 180 && path.last_handshake <= now + 5);
  const data = tunnel && peer.data_plane_confirmed && handshake;
  return <article className="rounded-xl border border-[var(--c-800)] p-4 space-y-2"><div className="flex flex-wrap justify-between gap-2"><strong>{peer.name}</strong><span className={data ? 'text-emerald-400 text-sm' : 'text-[var(--c-400)] text-sm'}>{data ? '近期 VPN 握手已确认' : peer.mode === 'transport-test' ? '传输测试 · 非 VPN' : 'VPN 数据面待确认'}</span></div>
    <p className="text-sm">虚拟 IP：{peer.ip || peer.virtual_ip || '未分配'} · {peer.os || '未知平台'} · {peer.groups.map(group => group.name).join('、') || '未分组'}</p>
    <p className="text-xs text-[var(--c-400)]">控制连接 {control ? '已连接' : '未确认'} · 中转连接 {control && peer.relay_connected ? '已连接' : '未确认'} · 系统 TUN {tunnel ? '已报告就绪' : '未确认'} · 最后心跳 {unixTime(peer.last_seen)}</p>
    {peer.paths.length === 0 && <p className="text-xs text-[var(--c-400)]">尚未观察到节点路径。</p>}
    {peer.paths.map(path => {
      const pathFresh = control && !!path.reported_at && Date.now() / 1000 - path.reported_at <= 45 && path.reported_at <= Date.now() / 1000 + 5;
      return <p className="text-xs text-[var(--c-400)]" key={path.peer_id}>至 {path.peer_id}：{pathFresh ? pathLabels[path.path] : '路径待确认'} · RTT {pathFresh && path.rtt_ms != null ? `${path.rtt_ms.toFixed(1)} ms` : '未测量'} · WireGuard 握手 {peer.mode === 'vpn' ? unixTime(path.last_handshake) : '未启用 VPN'}</p>;
    })}
  </article>;
}

export function FabricView({ canManage = true }: { canManage?: boolean }) {
  const account = useAccountState();
  const admin = canManage && adminAccess();
  const { data, error, loading, refetch } = usePolling(useCallback(async (signal: AbortSignal) => {
    const status = await fabricApi.status(signal);
    if (status.schema_version !== 1 || status.provider !== 'rlink') throw new Error('服务未返回支持的 R-Link Fabric 状态');
    const [peers, groups, enrollments, native] = await Promise.all([
      status.configured ? fabricApi.peers(signal) : Promise.resolve([]),
      status.capabilities.groups ? fabricApi.groups(signal) : Promise.resolve([]),
      admin && status.capabilities.enrollment ? fabricApi.enrollments(signal) : Promise.resolve([]),
      getNativeFabricStatus(),
    ]);
    return { status, peers, groups, enrollments, native };
  }, [admin]), 10000);
  const [name, setName] = useState('');
  const [group, setGroup] = useState('rlink-devices');
  const [ttl, setTtl] = useState(3600);
  const [oneOff, setOneOff] = useState<{ value: Enrollment; revision: number; base: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [revoke, setRevoke] = useState<string | null>(null);
  const active = useRef(false);
  const mutation = useRef<AbortController | null>(null);
  const pending = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; mutation.current?.abort(); }; }, []);
  useEffect(() => { setOneOff(null); setRevoke(null); mutation.current?.abort(); }, [account.revision]);
  useEffect(() => {
    if (!oneOff) return;
    const timer = setTimeout(() => setOneOff(null), Math.max(0, oneOff.value.expires_at * 1000 - Date.now()));
    return () => clearTimeout(timer);
  }, [oneOff]);
  const run = async (operation: (signal: AbortSignal, current: () => boolean) => Promise<void>) => {
    if (pending.current || !active.current || !canManage || !adminAccess()) return;
    const controller = new AbortController(); mutation.current = controller; pending.current = true;
    const revision = getAccountState().revision;
    const current = () => active.current && !controller.signal.aborted && getAccountState().revision === revision && adminAccess();
    setBusy(true); setActionError('');
    try { await operation(controller.signal, current); }
    catch (error) { if (current()) setActionError(error instanceof Error ? error.message : String(error)); }
    finally { pending.current = false; if (active.current) setBusy(false); }
  };
  const secret = admin && oneOff?.revision === account.revision && oneOff.base === serviceBase() && oneOff.value.expires_at * 1000 > Date.now() ? oneOff.value : null;
  return <section className="space-y-5 pb-6"><div className="flex justify-between items-start gap-3"><div><h2 className="text-xl font-semibold">R-Link 自研组网</h2><p className="text-sm text-[var(--c-400)]">节点优先尝试直连，无法打洞时使用中转。控制连接、路径探测与 VPN 握手分别验证。</p></div><button className={button} onClick={() => void refetch()}>刷新</button></div>
    {(error || actionError) && <p role="alert" className="text-red-400">{actionError || error?.message}</p>}{loading && <p role="status">正在读取自研组网状态…</p>}
    {data && <><p role="status" className="text-sm">控制面 {data.status.configured ? '已配置' : '未配置'} · {data.status.connected}/{data.status.peers} 节点近期心跳 · {data.status.mode_transport === 'vpn' ? '已观察到 VPN 模式节点' : data.status.mode_transport === 'transport-test' ? '目前只观察到传输测试，尚未确认 VPN 数据面' : '尚无 Agent 状态'} · 配置版本 {data.status.config_version}</p>
      <p className="text-xs text-[var(--c-400)]">中转为直连失败时的备用路径，会占用服务器带宽。RTT 和路径来自 Agent 报告，心跳或探测成功不能替代 WireGuard 握手。v1 同组成员互通。</p>
      <NativeStatus value={data.native} />
      <div className="space-y-3">{data.peers.map(peer => <Peer key={peer.id} peer={peer} />)}{data.peers.length === 0 && <p>暂无登记节点</p>}</div>
      {admin && data.status.capabilities.enrollment && <section className="rounded-xl border border-[var(--c-800)] p-4 space-y-4"><h3 className="font-semibold">一次性入网凭据</h3><p className="text-sm text-[var(--c-400)]">凭据仅在创建后显示一次，只能登记 1 台设备；不会保存在浏览器存储。过期或退出账户后隐藏。</p>
        <form className="grid gap-3 md:grid-cols-3" onSubmit={event => { event.preventDefault(); void run(async (signal, current) => {
          const result = await fabricApi.createEnrollment({ name: name.trim(), groups: [group], ttl_seconds: ttl }, signal);
          if (!current()) return;
          if (!result.enrollment_token || result.uses !== 1 || !Number.isFinite(result.expires_at)) throw new Error('服务未返回有效的一次性入网凭据');
          setOneOff({ value: result, revision: getAccountState().revision, base: serviceBase() }); setName(''); await refetch();
        }); }}><label className="text-sm">设备名称<input required maxLength={80} className={input} value={name} disabled={busy} onChange={event => setName(event.target.value)} /></label><label className="text-sm">入网分组<select className={input} value={group} disabled={busy} onChange={event => setGroup(event.target.value)}>{data.groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><label className="text-sm">有效秒数<input required type="number" min={300} max={86400} className={input} value={ttl} disabled={busy} onChange={event => setTtl(Number(event.target.value))} /></label><button className={button} disabled={busy || !name.trim() || !data.groups.some(item => item.id === group)}>生成一次性入网凭据</button></form>
        {secret && <div role="status" className="rounded border border-amber-500/40 p-4 space-y-2"><strong>立即复制入网凭据</strong><code className="block break-all select-all">{secret.enrollment_token}</code><p className="text-xs">到期：{unixTime(secret.expires_at)}。使用受信安装路径的 Agent enroll --server 配置服务地址，通过 --token-stdin 输入凭据。</p><button className={button} onClick={() => setOneOff(null)}>已保存，隐藏凭据</button></div>}
        {data.enrollments.map(item => <article key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--c-800)] pt-3 text-sm"><span>{item.name} · 使用 {item.used}/1 · {item.revoked ? '已撤销' : item.expires_at * 1000 <= Date.now() ? '已过期' : `到期 ${unixTime(item.expires_at)}`}</span>{data.status.capabilities.revocation && !item.revoked && item.used === 0 && item.expires_at * 1000 > Date.now() && <button className={button} disabled={busy} onClick={() => setRevoke(item.id)}>撤销凭据</button>}</article>)}
        {revoke && <div role="dialog" aria-label="确认撤销入网凭据" className="rounded border border-red-500/40 p-3"><p>撤销后该凭据不能登记设备。</p><button className={button} disabled={busy} onClick={() => void run(async (signal, current) => { await fabricApi.revokeEnrollment(revoke, signal); if (!current()) return; if (oneOff?.value.id === revoke) setOneOff(null); setRevoke(null); await refetch(); })}>确认撤销</button> <button className={button} disabled={busy} onClick={() => setRevoke(null)}>保留</button></div>}
      </section>}
    </>}
  </section>;
}

export default FabricView;
