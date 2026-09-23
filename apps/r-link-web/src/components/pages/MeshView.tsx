import { useCallback, useState } from 'react';
import { meshApi, type MeshPeer, type MeshGroup, type MeshKey, type MeshPolicy, type MeshNetwork, type PolicyInput, type ResourceInput, type RouterInput } from '../../api/mesh';
import { usePolling } from '../../api/usePolling';
import { ServiceField, ServiceMessage, serviceButton as button, serviceInput, useServiceAction } from '../common/ServiceControls';

type Tab = 'peers' | 'groups' | 'keys' | 'policies' | 'networks';
const tabs: { id: Tab; label: string }[] = [
  { id: 'peers', label: '节点' }, { id: 'groups', label: '分组' }, { id: 'keys', label: '入网密钥' },
  { id: 'policies', label: '访问策略' }, { id: 'networks', label: '网络路由' },
];
const emptyPolicy: PolicyInput = { name: '', source_group: '', destination_group: '', protocol: 'all', ports: [], enabled: true, bidirectional: false };
const emptyResource: ResourceInput = { name: '', address: '', description: '', enabled: true, groups: [] };
const emptyRouter: RouterInput = { peer: null, peer_groups: [], metric: 100, masquerade: true, enabled: true };

function editablePolicy(item: MeshPolicy) {
  const rule = item.rules[0];
  return item.description === 'R-Link managed policy' && item.rules.length === 1
    && rule.sources?.length === 1 && rule.destinations?.length === 1
    && !item.source_posture_checks?.length && !rule.port_ranges?.length
    && !rule.authorized_groups && !rule.sourceResource && !rule.destinationResource;
}

function GroupSelect({ label, groups, value, onChange, disabled }: { label: string; groups: MeshGroup[]; value: string; onChange: (value: string) => void; disabled?: boolean }) {
  return <label className="text-sm">{label}<select required className={serviceInput} value={value} disabled={disabled} onChange={e => onChange(e.target.value)}><option value="">选择分组</option>{groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>;
}

function NetworkDetail({ network, groups, peers }: { network: MeshNetwork; groups: MeshGroup[]; peers: MeshPeer[] }) {
  const { data, error, refetch } = usePolling(useCallback(async (signal: AbortSignal) => ({ resources: await meshApi.resources(network.id, signal), routers: await meshApi.routers(network.id, signal) }), [network.id]));
  const [resource, setResource] = useState<ResourceInput | null>(null);
  const [resourceId, setResourceId] = useState<string>();
  const [router, setRouter] = useState<RouterInput | null>(null);
  const [routerId, setRouterId] = useState<string>();
  const [remove, setRemove] = useState<{ name: string; action: () => Promise<unknown> } | null>(null);
  const action = useServiceAction();
  return <div className="mt-3 space-y-4 border-t border-[var(--c-700)] pt-4">
    <ServiceMessage error={action.error || error?.message} />
    <div><div className="flex justify-between"><h4 className="font-semibold">可访问资源</h4><button className={button} onClick={() => { setResourceId(undefined); setResource({ ...emptyResource }); }}>添加资源</button></div>
      {data?.resources.length === 0 && <p className="text-sm text-[var(--c-400)]">暂无资源。</p>}
      {data?.resources.map(item => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"><span className="break-all">{item.name} · {item.address} · {item.enabled ? '启用' : '停用'}</span><div className="flex gap-2"><button className={button} disabled={action.busy} onClick={() => { setResourceId(item.id); setResource({ name: item.name, address: item.address, description: item.description || '', enabled: item.enabled, groups: item.groups.map(group => group.id) }); }}>编辑</button><button className={button} disabled={action.busy} onClick={() => setRemove({ name: item.name, action: () => meshApi.deleteResource(network.id, item.id) })}>删除</button></div></div>)}
      {resource && <form className="grid gap-3 rounded border border-[var(--c-700)] p-3 md:grid-cols-2" onSubmit={e => { e.preventDefault(); void action.run(async () => { await meshApi.saveResource(network.id, resource, resourceId); setResource(null); await refetch(); }); }}>
        <ServiceField label="资源名称" required value={resource.name} disabled={action.busy} onChange={e => setResource({ ...resource, name: e.target.value })} />
        <ServiceField label="地址或 CIDR" required value={resource.address} disabled={action.busy} placeholder="192.168.1.0/24" onChange={e => setResource({ ...resource, address: e.target.value })} />
        <fieldset className="text-sm"><legend>资源分组（至少一个）</legend>{groups.map(group => <label className="mr-3 inline-flex gap-1" key={group.id}><input type="checkbox" checked={resource.groups.includes(group.id)} disabled={action.busy} onChange={e => setResource({ ...resource, groups: e.target.checked ? [...resource.groups, group.id] : resource.groups.filter(id => id !== group.id) })} />{group.name}</label>)}</fieldset>
        <label className="text-sm"><input type="checkbox" checked={resource.enabled} disabled={action.busy} onChange={e => setResource({ ...resource, enabled: e.target.checked })} /> 启用资源</label>
        <div><button className={button} disabled={action.busy || resource.groups.length === 0}>保存资源</button> <button type="button" className={button} onClick={() => setResource(null)}>取消</button></div>
      </form>}
    </div>
    <div><div className="flex justify-between"><h4 className="font-semibold">路由节点</h4><button className={button} onClick={() => { setRouterId(undefined); setRouter({ ...emptyRouter }); }}>添加路由</button></div>
      {data?.routers.length === 0 && <p className="text-sm text-[var(--c-400)]">暂无路由节点；配置资源后仍需路由节点才能访问。</p>}
      {data?.routers.map(item => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"><span>{peers.find(peer => peer.id === item.peer)?.name || item.peer || '节点组'} · metric {item.metric} · {item.enabled ? '启用' : '停用'}</span><div className="flex gap-2"><button className={button} disabled={action.busy} onClick={() => { setRouterId(item.id); setRouter({ peer: item.peer || null, peer_groups: item.peer_groups || [], metric: item.metric, masquerade: item.masquerade, enabled: item.enabled }); }}>编辑</button><button className={button} disabled={action.busy} onClick={() => setRemove({ name: item.peer || item.id, action: () => meshApi.deleteRouter(network.id, item.id) })}>删除</button></div></div>)}
      {router && <form className="grid gap-3 rounded border border-[var(--c-700)] p-3 md:grid-cols-2" onSubmit={e => { e.preventDefault(); void action.run(async () => { await meshApi.saveRouter(network.id, router, routerId); setRouter(null); await refetch(); }); }}>
        <label className="text-sm">路由节点<select className={serviceInput} disabled={action.busy} value={router.peer || ''} onChange={e => setRouter({ ...router, peer: e.target.value || null, peer_groups: [] })}><option value="">使用下方节点组或选择节点</option>{peers.map(peer => <option key={peer.id} value={peer.id}>{peer.name}</option>)}</select></label>
        <fieldset className="text-sm"><legend>或选择路由节点组</legend>{groups.map(group => <label className="mr-3 inline-flex gap-1" key={group.id}><input type="checkbox" checked={router.peer_groups.includes(group.id)} disabled={action.busy} onChange={e => setRouter({ ...router, peer: null, peer_groups: e.target.checked ? [...router.peer_groups, group.id] : router.peer_groups.filter(id => id !== group.id) })} />{group.name}</label>)}</fieldset>
        <ServiceField label="路由优先级（1–9999）" required type="number" min={1} max={9999} value={router.metric} disabled={action.busy} onChange={e => setRouter({ ...router, metric: Number(e.target.value) })} />
        <label className="text-sm"><input type="checkbox" checked={router.masquerade} disabled={action.busy} onChange={e => setRouter({ ...router, masquerade: e.target.checked })} /> 地址伪装（Masquerade）</label>
        <label className="text-sm"><input type="checkbox" checked={router.enabled} disabled={action.busy} onChange={e => setRouter({ ...router, enabled: e.target.checked })} /> 启用路由</label>
        <div><button className={button} disabled={action.busy || (!router.peer && router.peer_groups.length === 0)}>保存路由</button> <button type="button" className={button} onClick={() => setRouter(null)}>取消</button></div>
      </form>}
    </div>
    {remove && <div role="dialog" aria-label="确认删除组网资源" className="rounded border border-red-500/30 p-3"><p>删除 {remove.name}？</p><button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await remove.action(); setRemove(null); await refetch(); })}>确认删除</button> <button className={button} onClick={() => setRemove(null)}>保留</button></div>}
  </div>;
}

export function MeshView() {
  const { data, loading, error, refetch } = usePolling(useCallback(async (signal: AbortSignal) => {
    const status = await meshApi.status(signal);
    if (!status.configured) return { status, peers: [] as MeshPeer[], groups: [] as MeshGroup[], keys: [] as MeshKey[], policies: [] as MeshPolicy[], networks: [] as MeshNetwork[] };
    const [peers, groups, keys, policies, networks] = await Promise.all([
      meshApi.peers(signal), meshApi.groups(signal), meshApi.keys(signal), meshApi.policies(signal), meshApi.networks(signal),
    ]);
    return { status, peers, groups, keys, policies, networks };
  }, []), 10000);
  const [tab, setTab] = useState<Tab>('peers');
  const [peerName, setPeerName] = useState<{ id: string; name: string } | null>(null);
  const [group, setGroup] = useState<{ id?: string; name: string; peers: string[] } | null>(null);
  const [keyName, setKeyName] = useState('');
  const [keyGroup, setKeyGroup] = useState('');
  const [reusableKey, setReusableKey] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [policy, setPolicy] = useState<PolicyInput | null>(null);
  const [portsText, setPortsText] = useState('');
  const [policyId, setPolicyId] = useState<string>();
  const [network, setNetwork] = useState<{ id?: string; name: string; description: string } | null>(null);
  const [selectedNetwork, setSelectedNetwork] = useState<string | null>(null);
  const [remove, setRemove] = useState<{ name: string; action: () => Promise<unknown> } | null>(null);
  const action = useServiceAction();
  return <section className="space-y-5 pb-6">
    <div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-bold">NetBird 虚拟组网</h2><p className="mt-1 text-sm text-[var(--c-400)]">节点、分组、密钥和路由直接读取 NetBird 管理服务。</p></div><button className={button} disabled={action.busy} onClick={() => void refetch()}>刷新</button></div>
    <ServiceMessage error={action.error || error?.message} />
    {loading && <p role="status">正在读取组网状态…</p>}
    {data && !data.status.configured && <p role="status" className="rounded border border-amber-500/30 p-4">{data.status.reason}。请先部署 NetBird 并配置服务端访问令牌；当前没有已连接节点。</p>}
    {data?.status.configured && <>
      <p role="status" className="text-sm">管理服务可达 · {data.status.connected}/{data.status.peers} 节点当前连接管理端。该数字不代表节点之间已有直连。</p>
      <nav aria-label="组网管理" className="flex flex-wrap gap-2">{tabs.map(item => <button key={item.id} className={button} aria-current={tab === item.id ? 'page' : undefined} onClick={() => { setTab(item.id); setNewKey(null); }}>{item.label}</button>)}</nav>
      {tab === 'peers' && <div className="space-y-3">
        {data.peers.length === 0 && <p>暂无真实入网节点。请创建入网密钥，在目标机器安装 NetBird Agent 后加入。</p>}
        {data.peers.map(peer => <article className="rounded-xl border border-[var(--c-800)] p-4" key={peer.id}><div className="flex flex-wrap justify-between gap-2"><strong>{peer.name}</strong><span>{peer.connected ? '管理端在线' : '离线'}</span></div><p className="text-sm break-all">虚拟地址：{peer.ip || '尚未分配'} {peer.ipv6 || ''} · {peer.os || '未知系统'} · {peer.groups.map(group => group.name).join('、') || '未分组'}</p><p className="text-xs text-[var(--c-400)]">上次在线：{peer.last_seen ? new Date(peer.last_seen).toLocaleString() : '未知'}</p><button className={button} disabled={action.busy} onClick={() => setPeerName({ id: peer.id, name: peer.name })}>重命名</button> <button className={button} disabled={action.busy} onClick={() => setRemove({ name: peer.name, action: () => meshApi.deletePeer(peer.id) })}>移除节点</button></article>)}
        {peerName && <form className="flex gap-3 items-end" onSubmit={e => { e.preventDefault(); void action.run(async () => { await meshApi.renamePeer(peerName.id, peerName.name); setPeerName(null); await refetch(); }); }}><ServiceField label="节点名称" required value={peerName.name} onChange={e => setPeerName({ ...peerName, name: e.target.value })} /><button className={button} disabled={action.busy}>保存</button><button className={button} type="button" onClick={() => setPeerName(null)}>取消</button></form>}
      </div>}
      {tab === 'groups' && <div className="space-y-3"><button className={button} disabled={action.busy} onClick={() => setGroup({ name: '', peers: [] })}>新建分组</button>
        {data.groups.map(item => <article className="rounded-xl border border-[var(--c-800)] p-4" key={item.id}><strong>{item.name}</strong> · {item.peers_count ?? item.peers?.length ?? 0} 节点<br /><button className={button} disabled={action.busy} onClick={() => setGroup({ id: item.id, name: item.name, peers: item.peers?.map(peer => peer.id) || [] })}>编辑成员</button> <button className={button} disabled={action.busy} onClick={() => setRemove({ name: item.name, action: () => meshApi.deleteGroup(item.id) })}>删除</button></article>)}
        {group && <form className="rounded border border-[var(--c-700)] p-4 space-y-3" onSubmit={e => { e.preventDefault(); void action.run(async () => { await meshApi.saveGroup(group.name, group.peers, group.id); setGroup(null); await refetch(); }); }}><ServiceField label="分组名称" required value={group.name} onChange={e => setGroup({ ...group, name: e.target.value })} /><fieldset className="flex flex-wrap gap-4"><legend>组内节点</legend>{data.peers.map(peer => <label key={peer.id}><input type="checkbox" checked={group.peers.includes(peer.id)} onChange={e => setGroup({ ...group, peers: e.target.checked ? [...group.peers, peer.id] : group.peers.filter(id => id !== peer.id) })} /> {peer.name}</label>)}</fieldset><button className={button} disabled={action.busy}>保存分组</button> <button type="button" className={button} onClick={() => setGroup(null)}>取消</button></form>}
      </div>}
      {tab === 'keys' && <div className="space-y-3"><p className="text-sm text-[var(--c-400)]">入网密钥只在创建时完整显示一次。默认 24 小时有效、最多使用一次。</p>
        {newKey && <div role="status" className="rounded border border-amber-500/40 p-4 space-y-2"><strong>立即复制并安全保存此密钥</strong><code className="block break-all">{newKey}</code><p>在目标机器安装 Agent 后运行：<code className="break-all">netbird up --management-url {data.status.management_url} --setup-key &lt;上方密钥&gt;</code></p><button className={button} onClick={() => setNewKey(null)}>我已保存，关闭显示</button></div>}
        <form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void action.run(async () => { const created = await meshApi.createKey(keyName, keyGroup, reusableKey); if (!created.key) throw new Error('NetBird 未返回一次性密钥，请检查管理服务'); setNewKey(created.key); setKeyName(''); await refetch(); }); }}><ServiceField label="密钥名称" required value={keyName} onChange={e => setKeyName(e.target.value)} /><GroupSelect label="自动加入分组" groups={data.groups} value={keyGroup} onChange={setKeyGroup} /><label><input type="checkbox" checked={reusableKey} onChange={e => setReusableKey(e.target.checked)} /> 可用于 10 台设备</label><button className={button} disabled={action.busy || data.groups.length === 0}>创建入网密钥</button></form>
        {data.keys.map(key => <article className="rounded border border-[var(--c-800)] p-3" key={key.id}><strong>{key.name}</strong> · {key.revoked ? '已撤销' : key.valid ? '有效' : '失效'} · 到期 {key.expires ? new Date(key.expires).toLocaleString() : '未知'}<br />{!key.revoked && <button className={button} disabled={action.busy} onClick={() => setRemove({ name: key.name, action: () => meshApi.revokeKey(key.id) })}>撤销</button>} <button className={button} disabled={action.busy} onClick={() => setRemove({ name: key.name, action: () => meshApi.deleteKey(key.id) })}>删除</button></article>)}
      </div>}
      {tab === 'policies' && <div className="space-y-3"><p className="text-sm text-[var(--c-400)]">策略控制哪些分组能相互访问。NetBird 初始 Default 策略可能允许所有节点通信；新增限制策略前请检查并调整它。</p><button className={button} disabled={action.busy || data.groups.length < 1} onClick={() => { setPolicyId(undefined); setPolicy({ ...emptyPolicy }); setPortsText(''); }}>新建策略</button>
        {data.policies.map(item => <article className="rounded border border-[var(--c-800)] p-3" key={item.id}><strong>{item.name}</strong> · {item.enabled ? '启用' : '停用'} · {item.rules.length} 条规则<br /><button className={button} disabled={action.busy || !editablePolicy(item)} onClick={() => { const rule = item.rules[0]; setPolicyId(item.id); setPolicy({ name: item.name, source_group: rule.sources![0].id, destination_group: rule.destinations![0].id, protocol: (rule.protocol as PolicyInput['protocol']) || 'all', ports: (rule.ports || []).map(Number), enabled: item.enabled, bidirectional: rule.bidirectional || false }); setPortsText((rule.ports || []).join(',')); }}>编辑单规则策略</button> <button className={button} disabled={action.busy} onClick={() => setRemove({ name: item.name, action: () => meshApi.deletePolicy(item.id) })}>删除</button></article>)}
        {policy && <form className="grid gap-3 rounded border border-[var(--c-700)] p-4 md:grid-cols-2" onSubmit={e => { e.preventDefault(); void action.run(async () => { const ports = portsText.split(',').map(value => value.trim()).filter(Boolean); if (ports.some(value => !/^\d+$/.test(value))) throw new Error('端口应为逗号分隔的数字'); await meshApi.savePolicy({ ...policy, ports: ports.map(Number) }, policyId); setPolicy(null); await refetch(); }); }}><ServiceField label="策略名称" required value={policy.name} onChange={e => setPolicy({ ...policy, name: e.target.value })} /><GroupSelect label="来源分组" groups={data.groups} value={policy.source_group} onChange={value => setPolicy({ ...policy, source_group: value })} /><GroupSelect label="目标分组" groups={data.groups} value={policy.destination_group} onChange={value => setPolicy({ ...policy, destination_group: value })} /><label>协议<select className={serviceInput} value={policy.protocol} onChange={e => { setPolicy({ ...policy, protocol: e.target.value as PolicyInput['protocol'], ports: [] }); setPortsText(''); }}><option value="all">全部</option><option value="tcp">TCP</option><option value="udp">UDP</option><option value="icmp">ICMP</option></select></label><ServiceField label="端口（逗号分隔，可留空）" disabled={!['tcp', 'udp'].includes(policy.protocol)} value={portsText} onChange={e => setPortsText(e.target.value)} /><label><input type="checkbox" checked={policy.bidirectional} onChange={e => setPolicy({ ...policy, bidirectional: e.target.checked })} /> 双向</label><label><input type="checkbox" checked={policy.enabled} onChange={e => setPolicy({ ...policy, enabled: e.target.checked })} /> 启用</label><div><button className={button} disabled={action.busy}>保存策略</button> <button type="button" className={button} onClick={() => setPolicy(null)}>取消</button></div></form>}
      </div>}
      {tab === 'networks' && <div className="space-y-3"><p className="text-sm text-[var(--c-400)]">网络资源将目标网段分配给路由节点。目标机器必须运行 NetBird Agent，并允许转发流量。</p><button className={button} disabled={action.busy} onClick={() => setNetwork({ name: '', description: '' })}>新建网络</button>
        {network && <form className="grid gap-3 rounded border border-[var(--c-700)] p-3 md:grid-cols-2" onSubmit={e => { e.preventDefault(); void action.run(async () => { await meshApi.saveNetwork(network.name, network.description, network.id); setNetwork(null); await refetch(); }); }}><ServiceField label="网络名称" required value={network.name} onChange={e => setNetwork({ ...network, name: e.target.value })} /><ServiceField label="说明" value={network.description} onChange={e => setNetwork({ ...network, description: e.target.value })} /><div><button className={button} disabled={action.busy}>保存网络</button> <button type="button" className={button} onClick={() => setNetwork(null)}>取消</button></div></form>}
        {data.networks.map(item => <article className="rounded-xl border border-[var(--c-800)] p-4" key={item.id}><div className="flex justify-between"><strong>{item.name}</strong><span>{item.routing_peers_count ?? 0} 路由节点</span></div><p className="text-sm">{item.description}</p><div className="flex flex-wrap gap-2"><button className={button} onClick={() => setSelectedNetwork(selectedNetwork === item.id ? null : item.id)}>{selectedNetwork === item.id ? '收起' : '查看资源与路由'}</button><button className={button} onClick={() => setNetwork({ id: item.id, name: item.name, description: item.description || '' })}>编辑</button><button className={button} disabled={action.busy} onClick={() => setRemove({ name: item.name, action: () => meshApi.deleteNetwork(item.id) })}>删除</button></div>{selectedNetwork === item.id && <NetworkDetail network={item} groups={data.groups} peers={data.peers} />}</article>)}
      </div>}
      {remove && <div role="dialog" aria-label="确认组网操作" className="rounded border border-red-500/30 p-4 space-y-3"><p>确认对“{remove.name}”执行此操作？可能改变设备间的访问。</p><button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await remove.action(); setRemove(null); await refetch(); })}>确认执行</button> <button className={button} onClick={() => setRemove(null)}>取消</button></div>}
    </>}
  </section>;
}
export default MeshView;
