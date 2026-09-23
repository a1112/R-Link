import { useCallback, useState } from 'react';
import { servicesApi, type Domain, type DomainInput, type DomainCheck, type DNSRecord } from '../../api/services';
import { usePolling } from '../../api/usePolling';
import { ServiceField, ServiceMessage, ServiceLogs, serviceButton as button, serviceInput, useServiceAction } from '../common/ServiceControls';

const empty: DomainInput = { hostname: '', upstream_host: '127.0.0.1', upstream_port: 8080, enabled: true, zone_id: '' };
export function DomainView() {
  const { data, loading, error, refetch } = usePolling(useCallback(async (signal: AbortSignal) => ({ domains: await servicesApi.domains(signal), status: await servicesApi.domainStatus(signal), capabilities: await servicesApi.capabilities(signal) }), []), 5000);
  const [form, setForm] = useState<DomainInput | null>(null);
  const [editing, setEditing] = useState<string>();
  const [deleting, setDeleting] = useState<Domain | null>(null);
  const [logs, setLogs] = useState<string | null>(null);
  const [checks, setChecks] = useState<Record<string, DomainCheck>>({});
  const [dns, setDNS] = useState<{ domain: Domain; records: DNSRecord[] } | null>(null);
  const [dnsInput, setDNSInput] = useState<{ type: 'A' | 'AAAA' | 'CNAME'; content: string; ttl: number }>({ type: 'A', content: '', ttl: 1 });
  const [deleteRecord, setDeleteRecord] = useState<DNSRecord | null>(null);
  const action = useServiceAction();
  return <section className="space-y-5 pb-6">
    <div className="flex flex-wrap justify-between gap-3"><h2 className="text-xl font-bold">域名与 HTTPS</h2><button className={button} disabled={action.busy} onClick={() => { setEditing(undefined); setForm({ ...empty }); }}>添加域名</button></div>
    <p className="text-sm text-[var(--c-400)]">配置域名到 HTTP 服务的反向代理，由 Caddy 自动申请和续期证书。需将 DNS 指向此服务端，并开放公网 80/443 端口。保存配置后点击“应用 HTTPS”。</p>
    {data && <div className="space-y-2">
      {!data.capabilities.https.available && <p className="text-amber-400">{data.capabilities.https.reason}</p>}
      <p className="text-sm">HTTPS 进程：{data.status.state === 'running' ? '运行中' : data.status.state === 'error' ? '异常' : '已停止'}{data.status.pending_changes ? ' · 有尚未应用的配置' : ''}</p>
      {data.status.error && <p className="text-red-400">{data.status.error}</p>}
      <div className="flex flex-wrap gap-2"><button className={button} disabled={action.busy || !data.capabilities.https.available} onClick={() => void action.run(async () => { await servicesApi.domainAction('apply'); await refetch(); })}>应用 HTTPS</button><button className={button} disabled={action.busy || data.status.state !== 'running'} onClick={() => void action.run(async () => { await servicesApi.domainAction('stop'); await refetch(); })}>停止 HTTPS</button><button className={button} disabled={action.busy} onClick={() => void action.run(async () => setLogs((await servicesApi.domainLogs()).logs))}>服务日志</button></div>
      <p className="text-xs text-[var(--c-400)]">应用会短暂重启本平台管理的 HTTPS 服务。证书是否可用请使用各域名的“检测 DNS / 证书”。</p>
    </div>}
    <ServiceMessage error={action.error || error?.message} />
    {form && <form className="rounded-xl border border-[var(--c-700)] p-4 space-y-3" onSubmit={e => { e.preventDefault(); void action.run(async () => { await servicesApi.saveDomain(form, editing); setForm(null); await refetch(); }); }}>
      <fieldset disabled={action.busy} className="grid md:grid-cols-2 gap-3">
        <ServiceField label="域名" required maxLength={253} value={form.hostname} placeholder="app.example.com" onChange={e => setForm({ ...form, hostname: e.target.value })} />
        <ServiceField label="HTTP 目标主机" required value={form.upstream_host} onChange={e => setForm({ ...form, upstream_host: e.target.value })} />
        <ServiceField label="HTTP 目标端口" required type="number" min={1} max={65535} value={form.upstream_port} onChange={e => setForm({ ...form, upstream_port: Number(e.target.value) })} />
        <ServiceField label="Cloudflare Zone ID（可选）" pattern="[a-fA-F0-9]{32}" value={form.zone_id} onChange={e => setForm({ ...form, zone_id: e.target.value })} />
        <label className="text-sm"><input type="checkbox" checked={form.enabled} onChange={e => setForm({ ...form, enabled: e.target.checked })} /> 启用此域名</label>
      </fieldset>
      <button className={button} disabled={action.busy}>保存</button> <button type="button" className={button} disabled={action.busy} onClick={() => setForm(null)}>取消</button>
    </form>}
    {loading && <p role="status">正在读取域名…</p>}
    {data?.domains.length === 0 && <p className="text-[var(--c-400)]">暂无域名绑定。</p>}
    {data?.domains.map(item => <article key={item.id} className="rounded-xl border border-[var(--c-800)] p-4 space-y-3">
      <strong className="break-all">{item.hostname}</strong><p className="text-sm">HTTP 目标：{item.upstream_host}:{item.upstream_port} · {item.enabled ? '启用' : '禁用'}</p>
      <div className="flex flex-wrap gap-2">
        <button className={button} disabled={action.busy} onClick={() => { setEditing(item.id); setForm({ hostname: item.hostname, upstream_host: item.upstream_host, upstream_port: item.upstream_port, enabled: item.enabled, zone_id: item.zone_id }); }}>编辑</button>
        <button className={button} disabled={action.busy} onClick={() => void action.run(async () => { const result = await servicesApi.checkDomain(item.id); setChecks(previous => ({ ...previous, [item.id]: result })); })}>检测 DNS / 证书</button>
        <button className={button} disabled={action.busy || !item.zone_id || !data.status.dns_configured} onClick={() => void action.run(async () => { setDNS({ domain: item, records: await servicesApi.dns(item.id) }); setDeleteRecord(null); })}>DNS 记录</button>
        <button className={button} disabled={action.busy} onClick={() => setDeleting(item)}>删除绑定</button>
      </div>
      {checks[item.id] && <p className="text-sm break-all">{checks[item.id].checked_at} · DNS：{checks[item.id].addresses.join(', ') || '未解析'} · {checks[item.id].tls_valid ? `证书有效，到期：${checks[item.id].certificate_expires_at}` : checks[item.id].error}</p>}
    </article>)}
    <p className="text-xs text-[var(--c-400)]">如需在这里修改 DNS，请填写 Zone ID，并在服务端设置 R_LINK_CLOUDFLARE_TOKEN。其他 DNS 提供商可在其控制台手动配置。</p>
    {dns && <div className="rounded-xl border border-[var(--c-700)] p-4 space-y-3">
      <div className="flex justify-between"><strong>{dns.domain.hostname} DNS</strong><button disabled={action.busy} onClick={() => { setDNS(null); setDeleteRecord(null); }}>关闭 DNS</button></div>
      {dns.records.map(record => <div className="flex flex-wrap gap-3 text-sm" key={record.id}><span className="break-all">{record.type} {record.content} · TTL {record.ttl}</span><button disabled={action.busy} onClick={() => setDeleteRecord(record)}>删除记录</button></div>)}
      {dns.records.length === 0 && <p>暂无记录。</p>}
      <form className="grid md:grid-cols-[auto_1fr_auto_auto] gap-3 items-end" onSubmit={e => { e.preventDefault(); void action.run(async () => { await servicesApi.createDNS(dns.domain.id, dnsInput); setDNS({ ...dns, records: await servicesApi.dns(dns.domain.id) }); setDNSInput({ ...dnsInput, content: '' }); }); }}>
        <label>类型<select disabled={action.busy} className={serviceInput} value={dnsInput.type} onChange={e => setDNSInput({ ...dnsInput, type: e.target.value as 'A' | 'AAAA' | 'CNAME' })}><option>A</option><option>AAAA</option><option>CNAME</option></select></label>
        <ServiceField label="记录值" required disabled={action.busy} value={dnsInput.content} onChange={e => setDNSInput({ ...dnsInput, content: e.target.value })} />
        <ServiceField label="TTL（1 为自动）" type="number" min={1} max={86400} required disabled={action.busy} value={dnsInput.ttl} onChange={e => setDNSInput({ ...dnsInput, ttl: Number(e.target.value) })} />
        <button className={button} disabled={action.busy}>添加 DNS 记录</button>
      </form>
      {deleteRecord && <div role="dialog" aria-label="删除 DNS 记录"><p>删除 {deleteRecord.type} {deleteRecord.content}？会影响真实域名解析。</p><button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await servicesApi.deleteDNS(dns.domain.id, deleteRecord.id); setDeleteRecord(null); setDNS({ ...dns, records: await servicesApi.dns(dns.domain.id) }); })}>确认删除记录</button> <button className={button} disabled={action.busy} onClick={() => setDeleteRecord(null)}>保留记录</button></div>}
    </div>}
    {deleting && <div role="dialog" aria-label="删除域名绑定" className="rounded-xl border border-red-500/30 p-4"><p>删除“{deleting.hostname}”的绑定？应用 HTTPS 后生效，DNS 记录保留。</p><button className={button} disabled={action.busy} onClick={() => void action.run(async () => { await servicesApi.deleteDomain(deleting.id); if (dns?.domain.id === deleting.id) setDNS(null); setDeleting(null); await refetch(); })}>确认删除</button> <button className={button} disabled={action.busy} onClick={() => setDeleting(null)}>保留</button></div>}
    <ServiceLogs value={logs} close={() => setLogs(null)} />
  </section>;
}
export default DomainView;
