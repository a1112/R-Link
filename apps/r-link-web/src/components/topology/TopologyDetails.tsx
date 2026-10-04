import { useEffect, useRef } from 'react';
import { Box, CircuitBoard, ExternalLink, Folder, HardDrive, Monitor, Router, Server, Smartphone, Terminal, X, Pencil } from 'lucide-react';
import type { Device, DeviceType } from '../../api/devices';
import { connectionLabels, deviceAccessMode, devicePlatforms, deviceTypes, deviceWebUrl } from '../device-presentation';
import { displayTime, type TopologyNode } from './model';

export const deviceIcons = { computer: Monitor, server: Server, nas: HardDrive, mobile: Smartphone, router: Router, iot: CircuitBoard, other: Box } satisfies Record<DeviceType, typeof Monitor>;
export function StatusBadge({ node }: { node: Pick<TopologyNode, 'status' | 'statusLabel'> }) {
  return <span className={`topology-status is-${node.status}`}><i aria-hidden="true" />{node.statusLabel}</span>;
}
export function TopologyDetails({ node, onClose, onSsh, onManage, onRFile }: {
  node: TopologyNode; onClose: () => void; onSsh?: (device: Device) => void;
  onManage?: (device?: Device) => void; onRFile?: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
    if (window.matchMedia?.('(max-width: 850px)').matches) heading.current?.scrollIntoView?.({ block: 'start' });
  }, [node.id]);
  const Icon = deviceIcons[node.type];
  const device = node.device;
  const url = device ? deviceWebUrl(device) : null;
  const address = device ? `${device.host.includes(':') ? `[${device.host}]` : device.host}:${device.port}` : '未上报';
  const rows = device ? [
    ['系统', devicePlatforms[device.platform ?? 'unknown']], ['地址 / 端口', address], ['设备类型', deviceTypes[node.type]],
    ['设备来源', node.sourceLabel], ['最近在线', displayTime(device.last_seen)],
    ['端口检测', device.status === 'unchecked' ? '尚未检测' : device.status === 'reachable' ? `端口可达${device.latency_ms == null ? '' : ` · ${device.latency_ms} ms`}` : '端口不可达'],
    ['检测时间', displayTime(device.checked_at)],
    ...(device.source === 'gateway' ? [['网关状态', connectionLabels[device.gateway_status ?? 'unknown']], ['网关 ID', device.gateway_id || '未关联']] : []),
  ] : [['系统', node.subtitle], ['设备来源', 'R-File'], ['设备 ID', node.peer?.deviceId || '未上报'],
    ['连接方式', node.peer?.connectivity || '未上报'], ['信任状态', node.peer?.trustState || '未上报']];
  return <aside className="topology-details" aria-label="设备详情" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}>
    <div className="topology-details-title"><h2 ref={heading} tabIndex={-1}>设备详情</h2><button aria-label="关闭设备详情" onClick={onClose}><X size={20} /></button></div>
    <div className="topology-detail-device"><div className="topology-detail-icon"><Icon size={36} strokeWidth={1.4} /></div><div><h3>{node.name}</h3><StatusBadge node={node} /><p>{node.sourceLabel}</p></div></div>
    <h4 className="topology-section-title">概览</h4>
    <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {device?.tags?.length ? <div className="topology-tags">{device.tags.map(tag => <span key={tag}>{tag}</span>)}</div> : null}
    {device?.notes && <p className="topology-detail-note">{device.notes}</p>}
    {node.peer?.initiationBlockedReason && <p className="topology-detail-note">{node.peer.initiationBlockedReason}</p>}
    <div className="topology-detail-actions">
      <h4>可用操作</h4>
      {url && <a className="topology-button primary" href={url} target="_blank" rel="noreferrer"><ExternalLink size={16} />打开 Web 服务</a>}
      {device && deviceAccessMode(device) === 'ssh' && onSsh && <button className="topology-button primary" onClick={() => onSsh(device)}><Terminal size={16} />SSH 连接</button>}
      {node.source === 'rfile' && onRFile && <button className="topology-button primary" onClick={onRFile}><Folder size={16} />查看 R-File 服务</button>}
      {device && onManage && <button className="topology-button" onClick={() => onManage(device)}><Pencil size={15} />编辑设备</button>}
      {device && deviceAccessMode(device) === 'none' && <p className="topology-muted">此设备未提供可用的远程访问入口。</p>}
    </div>
  </aside>;
}
