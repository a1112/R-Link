import { useEffect, useRef } from 'react';
import { Box, CircuitBoard, ExternalLink, Folder, HardDrive, Monitor, Router, Server, Smartphone, Terminal, X, Pencil } from 'lucide-react';
import type { Device, DeviceType } from '../../api/devices';
import { connectionLabels, deviceAccessMode, devicePlatforms, deviceTypes, deviceWebUrl } from '../device-presentation';
import { displayTime, type TopologyNode } from './model';
import type { Annotation } from './interaction';
import { nativeFabricFresh } from '../../api/fabric';

export const deviceIcons = { computer: Monitor, server: Server, nas: HardDrive, mobile: Smartphone, router: Router, iot: CircuitBoard, other: Box } satisfies Record<DeviceType, typeof Monitor>;
export function StatusBadge({ node }: { node: Pick<TopologyNode, 'status' | 'statusLabel'> }) {
  return <span className={`topology-status is-${node.status}`}><i aria-hidden="true" />{node.statusLabel}</span>;
}
export function TopologyDetails({ node, annotation, focusOnOpen = true, onAnnotate, onClose, onSsh, onManage, onRFile }: {
  annotation?: Annotation;
  focusOnOpen?: boolean; onAnnotate?: () => void;
  node: TopologyNode; onClose: () => void; onSsh?: (device: Device) => void;
  onManage?: (device?: Device) => void; onRFile?: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!focusOnOpen) return;
    heading.current?.focus();
    if (window.matchMedia?.('(max-width: 850px)').matches) heading.current?.scrollIntoView?.({ block: 'start' });
  }, [node.id, focusOnOpen]);
  const Icon = deviceIcons[node.type];
  const device = node.device;
  const url = device ? deviceWebUrl(device) : null;
  const address = device ? `${device.host.includes(':') ? `[${device.host}]` : device.host}:${device.port}` : '未上报';
  const fabricFresh = nativeFabricFresh(node.client?.fabric);
  const fabricHandshake = node.client?.fabric?.mode === 'vpn' && fabricFresh ? Math.max(0, ...node.client.fabric.peers.map(peer => peer.last_handshake || 0)) : 0;
  const rows = node.client ? [
    ['主机名', node.client.hostname || (node.client.runtime === 'browser' ? '浏览器未提供' : '暂不可用')],
    ['系统', devicePlatforms[node.client.platform]], ['设备来源', node.sourceLabel],
    ['运行方式', node.client.runtime === 'desktop' ? '桌面客户端' : '浏览器'],
    ['NetBird 状态', node.clientMesh?.confirmed ? '已确认当前控制面的入网身份' : '尚未确认本电脑的 NetBird 入网身份'],
    ['NetBird 虚拟 IP', node.clientMesh?.confirmed ? node.clientMesh.ip || '未确认' : '未确认'],
    ['NetBird 本机控制面', node.clientMesh?.managementUrl || '未上报'],
    ['NetBird 服务控制面', node.clientMesh?.expectedManagementUrl || '暂不可用'],
    ...(node.client.fabric ? [
      ['自研 Agent 模式', node.client.fabric.mode === 'vpn' ? 'VPN' : '传输测试 · 非 VPN'],
      ['自研状态采样', fabricFresh ? '当前状态' : '过期或未运行'],
      ['自研控制连接', fabricFresh && node.client.fabric.control.connected ? '已连接' : '未确认'],
      ['自研系统 TUN', fabricFresh && node.client.fabric.mode === 'vpn' && node.client.fabric.tun.ready ? node.client.fabric.tun.name || '已报告就绪' : '未确认'],
      ['自研 Peer 路径', fabricFresh ? `直连 ${node.client.fabric.peers.filter(peer => peer.path === 'direct').length} · 中转 ${node.client.fabric.peers.filter(peer => peer.path === 'relay').length}` : '待确认'],
      ['自研最近 WG 握手', fabricHandshake > 0 ? new Date(fabricHandshake * 1000).toLocaleString() : '未上报真实 VPN 握手'],
      ['自研 VPN 状态', node.clientFabric?.confirmed ? '系统 TUN 与近期 WireGuard 握手已确认' : '待确认'],
      ['自研虚拟 IP', node.clientFabric?.confirmed ? node.clientFabric.ip || '未确认' : '未确认'],
      ['自研控制面', node.clientFabric?.managementUrl || '未配置'],
    ] : []),
    ...(device ? [['登记节点', device.name], ['地址 / 端口', address]] : []),
  ] : device ? [
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
    {annotation?.name && <p className="topology-detail-note">本机别名 · 原始名称：{node.device?.name || node.peer?.deviceName || node.peer?.deviceId}</p>}
    {annotation?.note && <p className="topology-detail-note">本机备注：{annotation.note}</p>}
    <h4 className="topology-section-title">概览</h4>
    <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {device?.tags?.length ? <div className="topology-tags">{device.tags.map(tag => <span key={tag}>{tag}</span>)}</div> : null}
    {device?.notes && <p className="topology-detail-note">{device.notes}</p>}
    {node.peer?.initiationBlockedReason && <p className="topology-detail-note">{node.peer.initiationBlockedReason}</p>}
    {node.client && <p className="topology-detail-note">这是正在使用 R-Link 的本电脑。{node.clientMesh?.reason || '完成 NetBird 入网并同步设备后，可查看登记节点的组网状态。'}</p>}
    {node.clientFabric && <p className="topology-detail-note">R-Link Fabric：{node.clientFabric.reason}</p>}
    <div className="topology-detail-actions">
      <h4>可用操作</h4>
      {url && <a className="topology-button primary" href={url} target="_blank" rel="noreferrer"><ExternalLink size={16} />打开 Web 服务</a>}
      {device && deviceAccessMode(device) === 'ssh' && onSsh && <button className="topology-button primary" onClick={() => onSsh(device)}><Terminal size={16} />SSH 连接</button>}
      {node.source === 'rfile' && onRFile && <button className="topology-button primary" onClick={onRFile}><Folder size={16} />查看 R-File 服务</button>}
      {device && onManage && <button className="topology-button" onClick={() => onManage(device)}><Pencil size={15} />编辑设备</button>}
      {onAnnotate && <button className="topology-button" onClick={onAnnotate}><Pencil size={15} />编辑显示名称与备注</button>}
      {device && deviceAccessMode(device) === 'none' && <p className="topology-muted">此设备未提供可用的远程访问入口。</p>}
    </div>
  </aside>;
}
