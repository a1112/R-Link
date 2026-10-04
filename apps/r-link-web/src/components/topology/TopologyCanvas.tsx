import { useEffect, useLayoutEffect, useRef, useState, type MutableRefObject, type ReactNode, type PointerEvent as ReactPointerEvent } from 'react';
import { Hand, Scan, Undo2, Redo2, RotateCcw, Pencil, Minus, Plus, Maximize, Network, Server, X } from 'lucide-react';
import type { Device } from '../../api/devices';
import { type layoutNodes, presenceLabels, type Presence } from './model';
import { deviceIcons, StatusBadge } from './TopologyDetails';
import { fitCamera, insideBox, toWorld, zoomAt, type Camera, type Point } from './interaction';
import type { useTopologyDocument } from './useTopologyDocument';

type Layout = ReturnType<typeof layoutNodes>;
type Store = ReturnType<typeof useTopologyDocument>;
type Gesture = { kind: 'pan' | 'nodes' | 'box'; pointer: number; start: Point; latest: Point; camera: Camera; ids: string[]; origins: Record<string, Point>; selection: string[]; additive: boolean; moved: boolean; nodeId?: string };
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
const midpoint = (a: Point, b: Point) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });

export function TopologyCanvas({ layout, visibleIds, selection, onSelection, store, serverName, serverStatus, onEditDevice, editRequest, nodeButtons, children }: {
  layout: Layout; visibleIds: string[]; selection: string[]; onSelection: (ids: string[], focusDetails?: boolean) => void; store: Store;
  editRequest?: { id: string; token: number } | null;
  serverName: string; serverStatus?: string; onEditDevice?: (device?: Device) => void;
  nodeButtons?: MutableRefObject<Map<string, HTMLButtonElement>>; children?: ReactNode;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const toolbar = useRef<HTMLDivElement>(null);
  const [toolbarHeight, setToolbarHeight] = useState(40);
  const [size, setSize] = useState({ width: 960, height: 640 });
  const [camera, setCamera] = useState<Camera>({ x: 0, y: 0, zoom: 1 });
  const cameraRef = useRef(camera); cameraRef.current = camera;
  const autoFit = useRef(true);
  const gesture = useRef<Gesture | null>(null);
  const pointers = useRef(new Map<number, Point>());
  const pinch = useRef<{ camera: Camera; center: Point; distance: number } | null>(null);
  const space = useRef(false);
  const [tool, setTool] = useState<'pan' | 'box'>('pan');
  const [preview, setPreview] = useState<Record<string, Point>>({});
  const [box, setBox] = useState<{ start: Point; end: Point } | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState(''), [note, setNote] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const visible = layout.nodes.filter(node => visibleIds.includes(node.id));
  const points = new Map([...layout.nodes, layout.hub].map(node => [node.id, preview[node.id] ?? store.document.positions[node.id] ?? node]));
  const actualPoints = new Map([...layout.nodes, layout.hub].map(node => [node.id, store.document.positions[node.id] ?? node]));
  const chosen = selection.length === 1 ? visible.find(node => node.id === selection[0]) : undefined;
  const editNode = visible.find(node => node.id === editing);
  const visibleKey = visibleIds.join('|');
  const applyCamera = (next: Camera) => { cameraRef.current = next; setCamera(next); };
  const fit = () => applyCamera(fitCamera([layout.hub, ...visible].map(node => actualPoints.get(node.id)!), size));
  const clearGesture = () => { gesture.current = null; pinch.current = null; pointers.current.clear(); setPreview({}); setBox(null); };
  const cancelGesture = () => {
    if (gesture.current?.kind === 'pan') applyCamera(gesture.current.camera);
    else if (pinch.current) applyCamera(pinch.current.camera);
    clearGesture();
  };

  useLayoutEffect(() => {
    const element = viewport.current;
    if (!element || typeof ResizeObserver === 'undefined') return;
    const update = () => { if (element.clientWidth && element.clientHeight) setSize({ width: element.clientWidth, height: element.clientHeight }); };
    update(); const observer = new ResizeObserver(update); observer.observe(element); return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => {
    if (!toolbar.current || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => setToolbarHeight(toolbar.current?.clientHeight || 40));
    observer.observe(toolbar.current); return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => { if (autoFit.current && !gesture.current && !pinch.current) fit(); }, [size, layout, store.document.positions, visibleKey]);
  useEffect(() => { clearGesture(); autoFit.current = true; fit(); }, [visibleKey]);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault(); if (gesture.current || pinch.current) return;
      const rect = element.getBoundingClientRect(), delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientHeight : 1);
      autoFit.current = false;
      applyCamera(zoomAt(cameraRef.current, { x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current.zoom * Math.exp(-Math.max(-500, Math.min(500, delta)) * .002)));
    };
    element.addEventListener('wheel', wheel, { passive: false });
    return () => element.removeEventListener('wheel', wheel);
  }, []);
  useEffect(() => {
    const cancel = () => { space.current = false; cancelGesture(); };
    window.addEventListener('blur', cancel); return () => window.removeEventListener('blur', cancel);
  }, []);
  useEffect(() => { if (editing && dialog.current && !dialog.current.open) dialog.current.showModal?.(); }, [editing]);
  useEffect(() => { if (editing && !editNode) setEditing(null); }, [editing, editNode]);
  useEffect(() => { if (editRequest) openEditor(editRequest.id); }, [editRequest]);
  const localPoint = (event: {clientX: number; clientY: number}) => {
    const rect = viewport.current!.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };
  const choose = (id: string, additive = false) => {
    onSelection(id === 'current' ? [] : additive ? selection.includes(id) ? selection.filter(value => value !== id) : [...selection, id] : [id], !additive);
  };
  const begin = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 && event.button !== 1) return;
    event.preventDefault(); viewport.current?.focus({ preventScroll: true });
    const point = localPoint(event);
    pointers.current.set(event.pointerId, point);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    if (pointers.current.size >= 2) {
      const [a, b] = [...pointers.current.values()];
      // A second finger changes the gesture into camera manipulation, not node editing.
      gesture.current = null; setPreview({}); setBox(null); autoFit.current = false;
      pinch.current = { camera: cameraRef.current, center: midpoint(a, b), distance: Math.max(1, distance(a, b)) }; return;
    }
    const nodeId = (event.target as Element).closest('[data-node-id]')?.getAttribute('data-node-id') || undefined;
    const additive = event.shiftKey || event.ctrlKey || event.metaKey;
    const pan = space.current || event.button === 1;
    const ids = nodeId ? selection.includes(nodeId) ? [...selection] : [nodeId] : [];
    gesture.current = { kind: pan ? 'pan' : nodeId ? 'nodes' : tool === 'box' || event.shiftKey ? 'box' : 'pan', pointer: event.pointerId,
      start: point, latest: point, camera: cameraRef.current, ids, origins: Object.fromEntries(actualPoints), selection: [...selection], additive, moved: false, nodeId };
  };
  const move = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!pointers.current.has(event.pointerId)) return;
    const point = localPoint(event); pointers.current.set(event.pointerId, point);
    const zoomGesture = pinch.current;
    if (zoomGesture && pointers.current.size >= 2) {
      const [a, b] = [...pointers.current.values()], center = midpoint(a, b);
      const next = zoomAt(zoomGesture.camera, zoomGesture.center, zoomGesture.camera.zoom * distance(a, b) / zoomGesture.distance);
      applyCamera({ ...next, x: next.x + center.x - zoomGesture.center.x, y: next.y + center.y - zoomGesture.center.y }); return;
    }
    const active = gesture.current; if (!active || active.pointer !== event.pointerId) return;
    active.latest = point; active.moved ||= distance(active.start, point) > 4;
    if (!active.moved) return;
    autoFit.current = false;
    const dx = point.x - active.start.x, dy = point.y - active.start.y;
    if (active.kind === 'pan') applyCamera({ ...active.camera, x: active.camera.x + dx, y: active.camera.y + dy });
    if (active.kind === 'nodes') setPreview(Object.fromEntries(active.ids.map(id => [id, { x: active.origins[id].x + dx / active.camera.zoom, y: active.origins[id].y + dy / active.camera.zoom }])));
    if (active.kind === 'box') setBox({ start: active.start, end: point });
  };
  const end = (event: ReactPointerEvent<HTMLDivElement>, cancel = false) => {
    pointers.current.delete(event.pointerId);
    if (pinch.current) {
      if (!pointers.current.size) clearGesture();
      // Ignore remaining fingers until all are lifted, preventing accidental node clicks.
      return;
    }
    const active = gesture.current;
    if (!active || active.pointer !== event.pointerId) return;
    if (!cancel) {
      if (!active.moved) {
        if (active.nodeId && active.kind === 'nodes') choose(active.nodeId, active.additive);
        else if (!active.additive) onSelection([]);
      } else if (active.kind === 'nodes') {
        const dx = (active.latest.x - active.start.x) / active.camera.zoom, dy = (active.latest.y - active.start.y) / active.camera.zoom;
        const positions = { ...store.document.positions };
        active.ids.forEach(id => { positions[id] = { x: active.origins[id].x + dx, y: active.origins[id].y + dy }; });
        store.commit({ ...store.document, positions });
        onSelection(active.ids.filter(id => id !== 'current'), false);
      } else if (active.kind === 'box') {
        const a = toWorld(active.start, active.camera), b = toWorld(active.latest, active.camera);
        const hits = visible.filter(node => insideBox(actualPoints.get(node.id)!, a, b)).map(node => node.id);
        onSelection([...new Set([...(active.additive ? active.selection : []), ...hits])], false);
      }
    } else if (active.kind === 'pan') applyCamera(active.camera);
    clearGesture();
  };
  const openEditor = (id = chosen?.id) => {
    if (!id) return;
    setName(store.document.annotations[id]?.name ?? ''); setNote(store.document.annotations[id]?.note ?? ''); setEditing(id);
  };
  const closeEditor = () => { setEditing(null); viewport.current?.focus({ preventScroll: true }); };
  const zoom = (factor: number) => { autoFit.current = false; applyCamera(zoomAt(cameraRef.current, { x: size.width / 2, y: size.height / 2 }, cameraRef.current.zoom * factor)); };
  const keyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if ((event.target as Element).closest('input,textarea,select,dialog')) return;
    const modifier = event.ctrlKey || event.metaKey;
    if (event.key === 'Escape') { cancelGesture(); onSelection([]); }
    else if (event.key === ' ' && event.target === viewport.current) { event.preventDefault(); space.current = true; }
    else if (modifier && event.key.toLowerCase() === 'a') { event.preventDefault(); onSelection(visibleIds, false); }
    else if (modifier && ['z','y'].includes(event.key.toLowerCase())) { event.preventDefault(); clearGesture(); event.shiftKey || event.key.toLowerCase() === 'y' ? store.redo() : store.undo(); }
    else if (event.key === '+' || event.key === '=') { event.preventDefault(); zoom(1.2); }
    else if (event.key === '-') { event.preventDefault(); zoom(1 / 1.2); }
    else if (event.key === '0') { event.preventDefault(); autoFit.current = true; fit(); }
    else if (event.key === 'F2' && chosen) { event.preventDefault(); openEditor(); }
    else if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)) {
      event.preventDefault(); autoFit.current = false;
      const step = event.shiftKey ? 30 : 10, delta = { x: event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0, y: event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0 };
      if (selection.length) {
        const positions = { ...store.document.positions };
        selection.forEach(id => { const point = actualPoints.get(id); if (point) positions[id] = { x: point.x + delta.x, y: point.y + delta.y }; });
        store.commit({ ...store.document, positions });
      } else applyCamera({ ...cameraRef.current, x: cameraRef.current.x - delta.x, y: cameraRef.current.y - delta.y });
    }
  };
  const hub = points.get('current')!;
  return <div className="topology-canvas-shell interactive-canvas" onKeyDown={keyDown} onKeyUp={event => { if (event.key === ' ') space.current = false; }}>
    <div className="topology-canvas-caption"><Network size={14} /><span>管理与发现关系</span><span className="topology-caption-count">{visible.length} 台设备</span></div>
    <div className="topology-tools" ref={toolbar} role="toolbar" aria-label="画布工具">
      <button aria-label="平移工具" title="平移（也可按住空格拖动）" aria-pressed={tool === 'pan'} onClick={() => setTool('pan')}><Hand size={16} /></button>
      <button aria-label="框选工具" title="框选（也可 Shift 拖动空白处）" aria-pressed={tool === 'box'} onClick={() => setTool('box')}><Scan size={16} /></button>
      <span className="tool-divider" />
      <button aria-label="撤销" title="撤销 Ctrl+Z" disabled={!store.canUndo} onClick={store.undo}><Undo2 size={16} /></button>
      <button aria-label="重做" title="重做 Ctrl+Shift+Z" disabled={!store.canRedo} onClick={store.redo}><Redo2 size={16} /></button>
      <button aria-label="恢复自动布局" title="恢复自动布局（可撤销）" disabled={!Object.keys(store.document.positions).length} onClick={() => { clearGesture(); autoFit.current = true; store.commit({ ...store.document, positions: {} }); }}><RotateCcw size={16} /></button>
      <button aria-label="编辑本机标注" title="编辑所选节点的本机标注 F2" disabled={!chosen} onClick={() => openEditor()}><Pencil size={16} /></button>
      {chosen?.device && onEditDevice && <button className="tool-text" aria-label="编辑所选设备" onClick={() => onEditDevice(chosen.device)}>设备配置</button>}
      {selection.length > 0 && <button className="tool-text" onClick={() => onSelection([])} aria-label="清除选择">已选 {selection.length} 台 <X size={12} /></button>}
    </div>
    <div className={`topology-viewport topology-interactive-viewport tool-${tool}`} ref={viewport} style={{top:toolbarHeight + 51}} tabIndex={0} aria-label="拓扑画布" aria-describedby="topology-interaction-help"
      onPointerDown={begin} onPointerMove={move} onPointerUp={event => end(event)} onPointerCancel={event => end(event, true)} onLostPointerCapture={event => { if (gesture.current?.pointer === event.pointerId) end(event, true); }}>
      <div data-testid="topology-stage" className="topology-stage" style={{ width: layout.width, height: layout.height, transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})` }}>
        <svg className="topology-edges" width={layout.width} height={layout.height} aria-hidden="true">{layout.edges.filter(edge => visibleIds.includes(edge.to) && (edge.from === 'current' || visibleIds.includes(edge.from))).map(edge => {
          const from = points.get(edge.from)!, to = points.get(edge.to)!;
          return <path key={edge.to} data-relation={edge.relation} className={selection.includes(edge.from) || selection.includes(edge.to) ? 'selected' : ''} strokeDasharray={edge.relation === 'gateway' ? undefined : '5 6'} d={`M ${from.x} ${from.y} C ${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x} ${to.y}`} />;
        })}</svg>
        <button className="topology-node topology-hub" data-node-id="current" aria-label="拖动当前服务端" style={{left:hub.x,top:hub.y}}><Server size={32} strokeWidth={1.4} /><div><strong title={serverName}>{serverName}</strong><span>当前 R-Link 服务端</span><small>{serverStatus || '管理 / 发现中心'}</small></div></button>
        {visible.map(node => {
          const Icon = deviceIcons[node.type], point = points.get(node.id)!, annotation = store.document.annotations[node.id];
          const label = annotation?.name || node.name;
          return <button key={node.id} data-node-id={node.id} ref={element => { if (element) nodeButtons?.current.set(node.id, element); else nodeButtons?.current.delete(node.id); }}
            className={`topology-node${selection.includes(node.id) ? ' selected' : ''}`} style={{ left: point.x, top: point.y }} aria-label={`查看设备：${label}`} aria-pressed={selection.includes(node.id)} title={`${label} · ${node.sourceLabel}${annotation?.note ? `\n本机备注：${annotation.note}` : ''}`}
            onClick={event => { if (event.detail === 0) choose(node.id, event.shiftKey || event.ctrlKey || event.metaKey); }}>
            <Icon size={33} strokeWidth={1.4} /><span className="topology-node-copy"><strong>{label}</strong><span>{node.subtitle}</span><StatusBadge node={node} /><small>{node.sourceLabel}{annotation?.name && ' · 本机别名'}</small></span>
          </button>;
        })}
      </div>
      {box && <div className="topology-selection-box" style={{left:Math.min(box.start.x,box.end.x),top:Math.min(box.start.y,box.end.y),width:Math.abs(box.end.x-box.start.x),height:Math.abs(box.end.y-box.start.y)}} />}
    </div>
    {children}
    <div className="topology-canvas-footer"><div className="topology-legend">{(['online','offline','unknown'] as Presence[]).map(status => <span key={status}><i className={`topology-dot is-${status}`} />{presenceLabels[status]}</span>)}</div>
      <div className="topology-zoom"><button aria-label="缩小" disabled={camera.zoom <= .1} onClick={() => zoom(1 / 1.2)}><Minus size={16} /></button><output aria-label="缩放比例">{Math.round(camera.zoom * 100)}%</output><button aria-label="放大" disabled={camera.zoom >= 3} onClick={() => zoom(1.2)}><Plus size={16} /></button><button aria-label="适应视图" title="适应视图 0" onClick={() => { autoFit.current = true; fit(); }}><Maximize size={16} /></button></div>
    </div>
    <p id="topology-interaction-help" className="topology-interaction-help">滚轮 / 双指缩放 · 拖动节点 · Shift 多选 / 框选 · 空格平移</p>
    {store.saveError && <p role="alert" className="topology-save-error">本机存储不可用，刷新后布局与标注可能丢失。</p>}
    {editing && editNode && <dialog ref={dialog} open={typeof HTMLDialogElement === 'undefined' || !HTMLDialogElement.prototype.showModal ? true : undefined} className="topology-annotation-dialog" aria-labelledby="topology-editor-title" onCancel={event => { event.preventDefault(); closeEditor(); }} onClose={closeEditor}>
      <form onSubmit={event => { event.preventDefault(); store.commit({ ...store.document, annotations: { ...store.document.annotations, [editing]: { name: name.trim(), note: note.trim() } } }); closeEditor(); }}>
        <h2 id="topology-editor-title">编辑本机标注</h2><p>仅保存在本机当前服务的拓扑中，不修改远端设备配置。</p>
        <p>原始名称：{editNode.device?.name || editNode.peer?.deviceName || editNode.name}</p>
        <label>显示名称<input autoFocus aria-label="显示名称" maxLength={80} value={name} placeholder="留空使用原始名称" onChange={event => setName(event.target.value)} /></label>
        <label>本机备注<textarea aria-label="本机备注" maxLength={1000} rows={3} value={note} onChange={event => setNote(event.target.value)} /></label>
        <div><button type="button" className="topology-button" onClick={closeEditor}>取消</button><button className="topology-button primary" type="submit">保存标注</button></div>
      </form>
    </dialog>}
  </div>;
}
