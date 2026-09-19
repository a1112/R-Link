import React, { useState, useRef, useEffect, useMemo } from "react";
import { 
  Cloud, Wifi, Server, Monitor, Laptop, HardDrive, 
  Plus, Minus, Maximize, ArrowLeft, Layout, Edit, 
  PlusCircle, Database, ChevronRight, Save, X, Cpu, Globe, Share2, Layers, Box, Router, ChevronUp, Check, Eye, EyeOff, Filter, Shield, Puzzle, MoreHorizontal, MessageSquare, Zap, Activity
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { NodeDetailModal } from "./NodeDetailModal";
import { toast } from "sonner@2.0.3";

// --- Mock Data for Topologies ---
const mockTopologies = [
  { id: 'topo1', name: '总部核心网络', desc: '北京总部IDC及核心交换层', nodeCount: 12, status: 'active', region: 'Beijing', icon: 'layout' },
  { id: 'topo2', name: '上海研发中心', desc: '研发测试环境与开发集群', nodeCount: 8, status: 'warning', region: 'Shanghai', icon: 'server' },
  { id: 'topo3', name: 'AWS 云端架构', desc: '生产环境云服务拓扑', nodeCount: 15, status: 'active', region: 'AWS-East', icon: 'cloud' },
  { id: 'topo4', name: '深圳办事处', desc: '办公网络与访客Wi-Fi', nodeCount: 5, status: 'offline', region: 'Shenzhen', icon: 'wifi' },
];

const getTopologyIcon = (iconName) => {
    switch(iconName) {
        case 'layout': return Layout;
        case 'server': return Server;
        case 'cloud': return Cloud;
        case 'wifi': return Wifi;
        case 'database': return Database;
        case 'globe': return Globe;
        case 'share': return Share2;
        case 'layers': return Layers;
        case 'box': return Box;
        default: return Layout;
    }
};

const CreateTopologyModal = ({ onClose, onCreate }) => {
    const [title, setTitle] = useState("");
    const [desc, setDesc] = useState("");
    const [selectedIcon, setSelectedIcon] = useState("layout");

    const icons = [
        { id: "layout", icon: Layout },
        { id: "server", icon: Server },
        { id: "cloud", icon: Cloud },
        { id: "wifi", icon: Wifi },
        { id: "database", icon: Database },
        { id: "globe", icon: Globe },
        { id: "share", icon: Share2 },
        { id: "layers", icon: Layers },
        { id: "box", icon: Box },
    ];

    const handleSubmit = () => {
        if (!title.trim()) {
            toast.error("请输入拓扑名称");
            return;
        }
        onCreate({ name: title, desc, icon: selectedIcon });
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--c-modal-overlay)] backdrop-blur-sm" onClick={onClose}>
            <motion.div 
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 20 }}
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-md bg-[var(--c-950)] border border-[var(--c-800)] rounded-xl shadow-2xl overflow-hidden"
            >
                <div className="p-4 border-b border-[var(--c-800)] flex justify-between items-center">
                    <h3 className="text-lg font-bold text-[var(--c-100)]">新建网络拓扑</h3>
                    <button onClick={onClose} className="text-[var(--c-500)] hover:text-[var(--c-100)] transition-colors">
                        <X size={20} />
                    </button>
                </div>
                
                <div className="p-6 space-y-4">
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-[var(--c-400)]">拓扑名称</label>
                        <input 
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="例如：北京数据中心"
                            className="w-full bg-[var(--c-900)] border border-[var(--c-800)] text-[var(--c-200)] text-sm rounded-lg px-3 py-2 outline-none focus:border-[var(--c-600)] transition-colors"
                        />
                    </div>
                    
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-[var(--c-400)]">描述 / 副标题</label>
                        <textarea 
                            value={desc}
                            onChange={(e) => setDesc(e.target.value)}
                            placeholder="简要描述该拓扑的用途或位置..."
                            rows={3}
                            className="w-full bg-[var(--c-900)] border border-[var(--c-800)] text-[var(--c-200)] text-sm rounded-lg px-3 py-2 outline-none focus:border-[var(--c-600)] transition-colors resize-none"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-medium text-[var(--c-400)]">选择图标</label>
                        <div className="grid grid-cols-5 gap-2">
                            {icons.map((item) => (
                                <button
                                    key={item.id}
                                    onClick={() => setSelectedIcon(item.id)}
                                    className={`p-2 rounded-lg flex flex-col items-center gap-1 transition-colors ${
                                        selectedIcon === item.id 
                                        ? "bg-[var(--c-800)] text-[var(--c-100)] ring-1 ring-[var(--c-600)]" 
                                        : "bg-[var(--c-900)] text-[var(--c-500)] hover:bg-[var(--c-800-50)] hover:text-[var(--c-300)]"
                                    }`}
                                >
                                    <item.icon size={20} />
                                    <span className="text-[10px] capitalize">{item.id}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="p-4 border-t border-[var(--c-800)] bg-[var(--c-900-50)] flex justify-end gap-2">
                    <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--c-400)] hover:text-[var(--c-200)] transition-colors">取消</button>
                    <button onClick={handleSubmit} className="px-3 py-1.5 text-xs bg-[var(--c-100)] text-[var(--c-950)] rounded-lg font-bold hover:bg-[var(--c-200)] transition-colors">创建拓扑</button>
                </div>
            </motion.div>
        </div>
    );
};

const mockTopologyData = {
  'topo1': {
    nodes: [
        { id: 'core-router', type: 'router', x: 400, y: 100, label: '核心路由器', status: 'active' },
        { id: 'core-switch-1', type: 'switch', x: 250, y: 250, label: '核心交换 A', status: 'active' },
        { id: 'core-switch-2', type: 'switch', x: 550, y: 250, label: '核心交换 B', status: 'active' },
        { id: 'server-cluster', type: 'server', x: 400, y: 400, label: '服务器集群', status: 'active' },
    ],
    links: [
        { source: 'core-router', target: 'core-switch-1', type: 'wan' },
        { source: 'core-router', target: 'core-switch-2', type: 'wan' },
        { source: 'core-switch-1', target: 'server-cluster', type: 'lan' },
        { source: 'core-switch-2', target: 'server-cluster', type: 'lan' },
    ]
  },
  'topo2': {
    nodes: [
      { id: 'gw', type: 'router', x: 400, y: 200, label: '研发网关', status: 'warning' },
      { id: 'dev1', type: 'desktop', x: 200, y: 400, label: '开发机 A', status: 'active' },
      { id: 'dev2', type: 'laptop', x: 600, y: 400, label: '测试机 B', status: 'offline' },
    ],
    links: [
      { source: 'gw', target: 'dev1', type: 'lan' },
      { source: 'gw', target: 'dev2', type: 'lan' },
    ]
  }
};

const defaultNodes = [
  { id: 'cloud', type: 'cloud', x: 400, y: 100, label: '互联网 / 云端', status: 'active' },
  { id: 'router', type: 'router', x: 400, y: 250, label: '核心网关', status: 'active' },
  { id: 'switch', type: 'switch', x: 400, y: 400, label: '交换机', status: 'active' },
  { id: 'pc1', type: 'desktop', x: 200, y: 550, label: '工作站 01', status: 'active' },
  { id: 'nas', type: 'server', x: 600, y: 550, label: 'NAS 存储', status: 'active' },
];

const defaultLinks = [
  { source: 'cloud', target: 'router', type: 'wan' },
  { source: 'router', target: 'switch', type: 'lan' },
  { source: 'switch', target: 'pc1', type: 'lan' },
  { source: 'switch', target: 'nas', type: 'lan' },
];

// --- Sub Component: Topology Card ---
const TopologyCard = ({ topo, onClick }) => {
  const Icon = getTopologyIcon(topo.icon);
  return (
  <div 
    onClick={onClick}
    className="group bg-[var(--c-900)] border border-[var(--c-800)] hover:border-[var(--c-600)] rounded-xl p-5 cursor-pointer transition-all duration-200 hover:-translate-y-1 hover:shadow-lg flex flex-col h-48"
  >
    <div className="flex items-start justify-between mb-4">
      <div className="w-10 h-10 rounded-lg bg-[var(--c-800-50)] flex items-center justify-center text-[var(--c-200)] group-hover:bg-[var(--c-800)] transition-colors">
        <Icon size={20} />
      </div>
      <div className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
         topo.status === 'active' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 
         topo.status === 'warning' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
         'bg-[var(--c-500-5)] text-[var(--c-500)] border-[var(--c-500-20)]'
      }`}>
        {topo.status === 'active' ? '运行正常' : topo.status === 'warning' ? '告警' : '离线'}
      </div>
    </div>
    
    <div>
      <h3 className="text-[var(--c-100)] font-bold mb-1 line-clamp-1">{topo.name}</h3>
      <p className="text-xs text-[var(--c-500)] line-clamp-2 h-8 leading-relaxed mb-1">
        {topo.desc}
      </p>
    </div>
    
    <div className="mt-auto pt-3 border-t border-[var(--c-800-50)] flex items-center justify-between text-xs text-[var(--c-500)]">
      <span className="flex items-center gap-1.5">
        <Database size={12} /> {topo.nodeCount} 节点
      </span>
      <span>{topo.region}</span>
    </div>
  </div>
)};

// --- Sub Component: Topology Canvas (The Actual Graph) ---
const TopologyCanvas = ({ topology, onBack }) => {
    const initialData = mockTopologyData[topology.id] || { nodes: defaultNodes, links: defaultLinks };
    
    const [nodes, setNodes] = useState(initialData.nodes);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const [links, setLinks] = useState(initialData.links);
    
    const [scale, setScale] = useState(1);
    const [offset, setOffset] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [draggingNode, setDraggingNode] = useState(null);
    const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 });
    const [hoveredNode, setHoveredNode] = useState(null);
    const [detailNode, setDetailNode] = useState(null);
    const [isEditing, setIsEditing] = useState(false);

    // --- View Filters ---
    const [layerMenuOpen, setLayerMenuOpen] = useState(false);
    const [selectedLayers, setSelectedLayers] = useState(['core', 'distribution', 'access']); // Default select all, exclude services
    
    const containerRef = useRef(null);

    // Filter Logic
    const getNodeLayer = (type) => {
        if (['cloud', 'router'].includes(type)) return 'core';
        if (['switch'].includes(type)) return 'distribution';
        if (['auth'].includes(type)) return 'auth';
        if (['plugin'].includes(type)) return 'plugin';
        return 'access';
    };

    const filteredNodes = nodes.filter(node => {
        const layer = getNodeLayer(node.type);
        return selectedLayers.includes(layer);
    });

    const handleWheel = (e) => {
        e.preventDefault();
        const container = containerRef.current;
        if (!container) return;

        const rect = container.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const delta = -e.deltaY;
        const factor = delta > 0 ? 1.1 : 0.9;
        let newScale = scale * factor;
        newScale = Math.max(0.1, Math.min(5, newScale));

        const newOffsetX = mouseX - (mouseX - offset.x) * (newScale / scale);
        const newOffsetY = mouseY - (mouseY - offset.y) * (newScale / scale);

        setScale(newScale);
        setOffset({ x: newOffsetX, y: newOffsetY });
    };

    const handleMouseDown = (e) => {
        if (e.button === 0) {
            setIsDragging(true);
            setLastMousePos({ x: e.clientX, y: e.clientY });
        }
    };

    const handleMouseMove = (e) => {
        if (draggingNode) {
            const dx = (e.clientX - lastMousePos.x) / scale;
            const dy = (e.clientY - lastMousePos.y) / scale;
            setNodes(nodes.map(n => n.id === draggingNode ? { ...n, x: n.x + dx, y: n.y + dy } : n));
            setLastMousePos({ x: e.clientX, y: e.clientY });
        } else if (isDragging) {
            const dx = e.clientX - lastMousePos.x;
            const dy = e.clientY - lastMousePos.y;
            setOffset({ x: offset.x + dx, y: offset.y + dy });
            setLastMousePos({ x: e.clientX, y: e.clientY });
        }
    };

    const handleMouseUp = () => {
        setIsDragging(false);
        setDraggingNode(null);
    };

    const handleZoomIn = () => setScale(Math.min(3, scale * 1.2));
    const handleZoomOut = () => setScale(Math.max(0.5, scale / 1.2));
    const handleFitView = () => { setScale(1); setOffset({ x: 0, y: 0 }); };

    const getNodeCenter = (node) => ({ x: node.x + 32, y: node.y + 32 });

    const getNodeIcon = (type) => {
        switch(type) {
            case 'cloud': return <Cloud size={24} className="text-blue-400" />;
            case 'router': return <Router size={24} className="text-violet-400" />;
            case 'switch': return <Server size={24} className="text-indigo-400" />;
            case 'desktop': return <Monitor size={24} className="text-[var(--c-200)]" />;
            case 'laptop': return <Laptop size={24} className="text-[var(--c-200)]" />;
            case 'server': return <HardDrive size={24} className="text-amber-400" />;
            case 'auth': return <Shield size={24} className="text-rose-400" />;
            case 'plugin': return <Puzzle size={24} className="text-violet-400" />;
            default: return <Server size={24} />;
        }
    };

    // Calculate links
    // Fix: use state links, do not redeclare
    const baseFilteredLinks = links.filter(link => {
        const sourceVisible = filteredNodes.some(n => n.id === link.source);
        const targetVisible = filteredNodes.some(n => n.id === link.target);
        return sourceVisible && targetVisible;
    });

    // Auto-connect services to cloud if visible
    const serviceNodes = filteredNodes.filter(n => ['auth', 'plugin'].includes(n.type));
    const cloudNode = filteredNodes.find(n => n.type === 'cloud');
    
    // Generate virtual links for services that don't have explicit links to a cloud node
    const virtualLinks = [];
    if (cloudNode) {
        serviceNodes.forEach(serviceNode => {
             // Check if there is already a link
             const hasLink = baseFilteredLinks.some(l => 
                (l.source === serviceNode.id && l.target === cloudNode.id) || 
                (l.target === serviceNode.id && l.source === cloudNode.id)
             );
             
             if (!hasLink) {
                 virtualLinks.push({
                     source: serviceNode.id,
                     target: cloudNode.id,
                     type: 'virtual'
                 });
             }
        });
    }

    const filteredLinks = [...baseFilteredLinks, ...virtualLinks];

    const getHoverPosition = () => {
        if (!hoveredNode) return {};
        const left = (hoveredNode.x * scale) + offset.x + (80 * scale); 
        const top = (hoveredNode.y * scale) + offset.y;
        return { left, top };
    };

    const handleAddNode = (type) => {
        const id = `node-${Date.now()}`;
        const newNode = {
            id,
            type: type === 'internet' ? 'cloud' : type === 'iot' ? 'server' : type === 'auth' ? 'auth' : type === 'plugin' ? 'plugin' : 'desktop',
            x: 100 - offset.x / scale, // Rough center logic or top left relative
            y: 100 - offset.y / scale,
            label: type === 'internet' ? 'New Cloud Service' : type === 'auth' ? 'Auth Server' : type === 'plugin' ? 'Plugin Service' : 'New Device',
            status: 'active'
        };
        setNodes([...nodes, newNode]);
        toast.success("节点已添加", { description: "请拖拽节点至合适位置" });
    };

    return (
        <div className="h-[calc(100vh-8rem)] flex flex-col bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl overflow-hidden relative select-none animate-in fade-in zoom-in-95 duration-300">
            {/* Header / Breadcrumb Overlay */}
             <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
                <button 
                    onClick={onBack}
                    className="p-2 bg-[var(--c-900)] border border-[var(--c-700)] rounded-lg text-[var(--c-400)] hover:text-[var(--c-100)] hover:bg-[var(--c-800)] transition-colors shadow-lg"
                >
                    <ArrowLeft size={16} />
                </button>

                
                <button 
                    onClick={() => setIsEditing(!isEditing)}
                    className={`p-2 border rounded-lg transition-colors shadow-lg ${
                        isEditing 
                        ? "bg-blue-500/10 border-blue-500/50 text-blue-400" 
                        : "bg-[var(--c-900)] border-[var(--c-700)] text-[var(--c-400)] hover:text-[var(--c-100)] hover:bg-[var(--c-800)]"
                    }`}
                >
                    <Edit size={16} />
                </button>
            </div>

            {/* Right Info Panel */}
            <div className="absolute top-4 right-4 z-20 flex flex-col items-end gap-2 w-64 animate-in slide-in-from-right-4 duration-500">
                <div className="bg-[var(--c-900-90)] backdrop-blur border border-[var(--c-700)] rounded-xl p-4 shadow-lg w-full">
                    <div className="flex items-start justify-between mb-3">
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <h2 className="text-sm font-bold text-[var(--c-100)]">{topology.name}</h2>
                                <span className={`w-2 h-2 rounded-full ${
                                    topology.status === 'active' ? 'bg-emerald-500' : 'bg-amber-500'
                                }`} />
                            </div>
                            <div className="text-[10px] text-[var(--c-500)] leading-tight">{topology.desc}</div>
                        </div>
                    </div>
                    
                    <div className="h-px bg-[var(--c-800)] w-full my-3" />
                    
                    <div className="flex items-center justify-between">
                         <div className="flex gap-4">
                             <div className="flex flex-col">
                                 <span className="text-[10px] text-[var(--c-500)]">节点</span>
                                 <span className="text-xs font-bold text-[var(--c-200)] font-mono">{nodes.length}</span>
                             </div>
                             <div className="flex flex-col">
                                 <span className="text-[10px] text-[var(--c-500)]">连接</span>
                                 <span className="text-xs font-bold text-[var(--c-200)] font-mono">{links.length}</span>
                             </div>
                             <div className="flex flex-col">
                                 <span className="text-[10px] text-[var(--c-500)]">负载</span>
                                 <div className="flex items-center gap-1">
                                     <Activity size={10} className="text-emerald-500" />
                                     <span className="text-xs font-bold text-emerald-500 font-mono">24%</span>
                                 </div>
                             </div>
                         </div>
                         
                         <button className="flex items-center justify-center w-8 h-8 rounded-lg bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-400)] hover:text-[var(--c-100)] transition-colors relative group">
                            <MessageSquare size={14} />
                            <span className="absolute top-0 right-0 w-2 h-2 bg-red-500 rounded-full border-2 border-[var(--c-900)] translate-x-1/4 -translate-y-1/4"></span>
                         </button>
                    </div>
                </div>
            </div>

            {/* Editing Palette */}
            <AnimatePresence>
                {isEditing && (
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="absolute top-20 left-4 z-20 bg-[var(--c-900)] border border-[var(--c-700)] rounded-xl shadow-xl p-2 flex flex-col gap-1 w-40"
                    >
                        <div className="text-[10px] font-bold text-[var(--c-500)] px-1 mb-1 uppercase tracking-wider">添加节点</div>
                        <button onClick={() => handleAddNode('device')} className="flex items-center gap-2 p-2 text-xs text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors text-left">
                            <Monitor size={14} /> 设备管理引用
                        </button>
                         <button onClick={() => handleAddNode('internet')} className="flex items-center gap-2 p-2 text-xs text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors text-left">
                            <Cloud size={14} /> 互联网服务
                        </button>
                         <button onClick={() => handleAddNode('iot')} className="flex items-center gap-2 p-2 text-xs text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors text-left">
                            <Cpu size={14} /> IoT 智能设备
                        </button>
                         <button onClick={() => handleAddNode('auth')} className="flex items-center gap-2 p-2 text-xs text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors text-left">
                            <Shield size={14} /> 认证服务节点
                        </button>
                         <button onClick={() => handleAddNode('plugin')} className="flex items-center gap-2 p-2 text-xs text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors text-left">
                            <Puzzle size={14} /> 插件服务节点
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>
            
            {/* Detail Modal */}
            <AnimatePresence>
                {detailNode && (
                    <NodeDetailModal node={detailNode} onClose={() => setDetailNode(null)} />
                )}
            </AnimatePresence>

            {/* Canvas Area */}
            <div 
                ref={containerRef}
                className="flex-1 overflow-hidden cursor-move bg-[var(--c-950)] relative"
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={() => {
                    handleMouseUp();
                    setHoveredNode(null);
                }}
            >
                <div 
                    className="absolute inset-0 origin-top-left will-change-transform"
                    style={{ 
                        transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${scale})`
                    }}
                >
                    {/* Grid Background */}
                    <div className="absolute -inset-[4000px] opacity-10 pointer-events-none" 
                        style={{
                            backgroundImage: 'radial-gradient(circle, var(--c-500) 1px, transparent 1px)',
                            backgroundSize: '24px 24px'
                        }}
                    ></div>

                    {/* Connections */}
                    <svg className="absolute top-0 left-0 w-[4000px] h-[4000px] pointer-events-none overflow-visible">
                         {filteredLinks.map((link, i) => {
                             const sourceNode = filteredNodes.find(n => n.id === link.source);
                             const targetNode = filteredNodes.find(n => n.id === link.target);
                             if (!sourceNode || !targetNode) return null;
                             
                             const start = getNodeCenter(sourceNode);
                             const end = getNodeCenter(targetNode);
                             
                             return (
                                 <g key={i}>
                                     <line 
                                         x1={start.x} y1={start.y} 
                                         x2={end.x} y2={end.y} 
                                         stroke={link.type === 'virtual' ? "var(--c-600)" : "var(--c-700)"}
                                         strokeWidth="2"
                                         strokeDasharray={link.type === 'wan' || link.type === 'virtual' ? "5,5" : "0"}
                                         className={link.type === 'virtual' ? 'opacity-50' : ''}
                                     />
                                 </g>
                             )
                         })}
                    </svg>

                    {/* Nodes */}
                    {filteredNodes.map(node => (
                        <div
                            key={node.id}
                            onMouseDown={(e) => {
                                e.stopPropagation();
                                setHoveredNode(null);
                                if (isEditing) {
                                     setDraggingNode(node.id);
                                     setLastMousePos({ x: e.clientX, y: e.clientY });
                                } else {
                                     setDraggingNode(node.id);
                                     setLastMousePos({ x: e.clientX, y: e.clientY });
                                }
                            }}
                            onMouseEnter={() => !draggingNode && setHoveredNode(node)}
                            onMouseLeave={() => setHoveredNode(null)}
                            onDoubleClick={(e) => {
                                e.stopPropagation();
                                setDetailNode(node);
                                setHoveredNode(null);
                            }}
                            className={`absolute flex flex-col items-center gap-2 p-2 rounded-xl border-2 cursor-grab active:cursor-grabbing group w-24 transition-colors duration-200
                                ${node.status === 'active' ? 'border-[var(--c-800)] bg-[var(--c-900)]' : 'border-amber-900/30 bg-amber-950/10'}
                                hover:border-blue-500/50 hover:shadow-[0_0_20px_rgba(59,130,246,0.15)]
                            `}
                            style={{ 
                                transform: `translate3d(${node.x}px, ${node.y}px, 0)`,
                                touchAction: 'none'
                            }}
                        >
                             <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-lg transition-all
                                 ${node.status === 'active' ? 'bg-[var(--c-800)] group-hover:bg-[var(--c-700)]' : 'bg-amber-900/20'}
                             `}>
                                 {getNodeIcon(node.type)}
                             </div>
                             
                             <div className="text-center">
                                 <div className="text-[10px] font-bold text-[var(--c-200)] leading-tight truncate w-full px-1">{node.label}</div>
                                 <div className="text-[9px] text-[var(--c-500)] scale-90">{node.type}</div>
                             </div>

                             {/* Status Indicator */}
                             <div className={`absolute -top-1 -right-1 w-3 h-3 rounded-full border-2 border-[var(--c-950)] ${
                                 node.status === 'active' ? 'bg-emerald-500' : 'bg-amber-500'
                             }`} />
                        </div>
                    ))}
                </div>

                {/* Zoom Controls */}
                <div className="flex flex-col gap-1 bg-[var(--c-800-90)] backdrop-blur border border-[var(--c-700)] p-1 rounded-lg shadow-xl w-fit self-end absolute bottom-4 left-4 z-20">
                    <button onClick={handleZoomIn} className="p-2 text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors"><Plus size={20} /></button>
                    <button onClick={handleZoomOut} className="p-2 text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors"><Minus size={20} /></button>
                    <button onClick={handleFitView} className="p-2 text-[var(--c-300)] hover:text-[var(--c-white)] hover:bg-[var(--c-700)] rounded-md transition-colors"><Maximize size={20} /></button>
                </div>
            </div>

            {/* Bottom Right - View Controls (New Feature) */}
            <div className="absolute bottom-4 right-4 z-20 flex items-end gap-2">
                {/* Layer Selection Dropup */}
                <div className="relative">
                    <AnimatePresence>
                        {layerMenuOpen && (
                            <motion.div
                                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                                className="absolute bottom-full right-0 mb-2 w-48 bg-[var(--c-900)] border border-[var(--c-700)] rounded-xl shadow-2xl overflow-visible flex flex-col p-1"
                            >
                                <div className="text-[10px] font-bold text-[var(--c-500)] px-2 py-1 uppercase tracking-wider">显示层级 (多选)</div>
                                {[
                                    { id: 'core', label: '核心架构', icon: Cloud },
                                    { id: 'distribution', label: '汇聚层', icon: Share2 },
                                    { id: 'access', label: '终端接入', icon: Monitor },
                                ].map((layer) => {
                                    const isSelected = selectedLayers.includes(layer.id);
                                    return (
                                        <button
                                            key={layer.id}
                                            onClick={() => {
                                                if (isSelected) {
                                                    setSelectedLayers(selectedLayers.filter(id => id !== layer.id));
                                                } else {
                                                    setSelectedLayers([...selectedLayers, layer.id]);
                                                }
                                            }}
                                            className={`flex items-center justify-between px-2 py-1.5 rounded-lg text-xs transition-colors mb-0.5 ${
                                                isSelected
                                                ? "bg-[var(--c-800)] text-[var(--c-100)]"
                                                : "text-[var(--c-400)] hover:bg-[var(--c-800-50)] hover:text-[var(--c-200)]"
                                            }`}
                                        >
                                            <div className="flex items-center gap-2">
                                                <layer.icon size={14} />
                                                {layer.label}
                                            </div>
                                            {isSelected && <Check size={12} className="text-blue-500" />}
                                        </button>
                                    );
                                })}
                                
                                <div className="my-1 border-t border-[var(--c-800)]" />
                                
                                <div className="relative group/more">
                                    <button
                                        onClick={(e) => e.stopPropagation()}
                                        className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs transition-colors ${
                                            ['auth', 'plugin'].some(id => selectedLayers.includes(id))
                                            ? "bg-[var(--c-800)] text-[var(--c-100)]"
                                            : "text-[var(--c-400)] hover:bg-[var(--c-800-50)] hover:text-[var(--c-200)]"
                                        }`}
                                    >
                                        <div className="flex items-center gap-2">
                                            <MoreHorizontal size={14} />
                                            更多...
                                        </div>
                                        <ChevronRight size={12} />
                                    </button>

                                    {/* Submenu */}
                                    <div className="absolute bottom-0 right-full mr-1 w-40 bg-[var(--c-900)] border border-[var(--c-700)] rounded-xl shadow-xl overflow-hidden flex flex-col p-1 hidden group-hover/more:flex">
                                        {[
                                            { id: 'auth', label: '认证服务', icon: Shield },
                                            { id: 'plugin', label: '插件服务', icon: Puzzle },
                                        ].map((layer) => {
                                            const isSelected = selectedLayers.includes(layer.id);
                                            return (
                                                <button
                                                    key={layer.id}
                                                    onClick={(e) => {
                                                        e.stopPropagation(); // Prevent closing parent menu if handled
                                                        if (isSelected) {
                                                            setSelectedLayers(selectedLayers.filter(id => id !== layer.id));
                                                        } else {
                                                            setSelectedLayers([...selectedLayers, layer.id]);
                                                        }
                                                    }}
                                                    className={`flex items-center justify-between px-2 py-1.5 rounded-lg text-xs transition-colors mb-0.5 ${
                                                        isSelected
                                                        ? "bg-[var(--c-800)] text-[var(--c-100)]"
                                                        : "text-[var(--c-400)] hover:bg-[var(--c-800-50)] hover:text-[var(--c-200)]"
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-2">
                                                        <layer.icon size={14} />
                                                        {layer.label}
                                                    </div>
                                                    {isSelected && <Check size={12} className="text-blue-500" />}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                    
                    <button
                        onClick={() => setLayerMenuOpen(!layerMenuOpen)}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border shadow-xl backdrop-blur transition-all ${
                            layerMenuOpen
                            ? "bg-[var(--c-800)] border-[var(--c-600)] text-[var(--c-100)]"
                            : "bg-[var(--c-800-90)] border-[var(--c-700)] text-[var(--c-300)] hover:text-[var(--c-100)] hover:bg-[var(--c-700)]"
                        }`}
                    >
                        <Filter size={16} />
                        <span className="text-xs font-medium">
                            视图过滤
                        </span>
                        <ChevronUp size={14} className={`transition-transform duration-200 ${layerMenuOpen ? 'rotate-180' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Hover Tooltip */}
            <AnimatePresence>
                {hoveredNode && !isDragging && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, x: -10 }}
                        animate={{ opacity: 1, scale: 1, x: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute z-30 w-56 pointer-events-none"
                        style={getHoverPosition()}
                    >
                         <div className="bg-[var(--c-950-85)] backdrop-blur-md border border-[var(--c-800)] rounded-xl shadow-xl p-4 text-left">
                             <div className="flex items-center justify-between mb-2">
                                 <span className="text-xs font-bold text-[var(--c-100)]">{hoveredNode.label}</span>
                                 <span className={`w-2 h-2 rounded-full ${
                                    hoveredNode.status === 'active' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-amber-500'
                                 }`} />
                             </div>
                             <div className="space-y-1.5">
                                 <div className="flex justify-between text-[10px]">
                                     <span className="text-[var(--c-500)]">ID</span>
                                     <span className="text-[var(--c-300)] font-mono">{hoveredNode.id}</span>
                                 </div>
                                 <div className="flex justify-between text-[10px]">
                                     <span className="text-[var(--c-500)]">Type</span>
                                     <span className="text-[var(--c-300)] capitalize">{hoveredNode.type}</span>
                                 </div>
                                 <div className="pt-1 mt-1 border-t border-[var(--c-800-50)] text-[10px] text-[var(--c-500)] text-center">
                                    双击查看详情
                                 </div>
                             </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export function TopologyView() {
    const [activeTopology, setActiveTopology] = useState(null);
    const [topologies, setTopologies] = useState(mockTopologies);
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

    const handleCreateTopology = (newTopo) => {
        const id = `topo-${Date.now()}`;
        const created = {
            id,
            ...newTopo,
            nodeCount: 0,
            status: 'active',
            region: 'Local',
        };
        setTopologies([...topologies, created]);
        toast.success("拓扑创建成功");
    };

    if (activeTopology) {
        return <TopologyCanvas topology={activeTopology} onBack={() => setActiveTopology(null)} />;
    }

    return (
        <div className="h-full flex flex-col overflow-hidden">
            <div className="flex items-center justify-between mb-6">
                 <div>
                    <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">网络拓扑管理</h2>
                    <p className="text-xs text-[var(--c-500)] mt-1">可视化管理虚拟局域网与设备连接</p>
                 </div>
                 <button 
                    onClick={() => setIsCreateModalOpen(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-[var(--c-100)] text-[var(--c-950)] rounded-lg text-sm font-bold hover:bg-[var(--c-200)] transition-colors shadow-lg shadow-[rgba(255,255,255,0.1)]"
                 >
                     <PlusCircle size={16} />
                     新建拓扑
                 </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 overflow-y-auto pb-20 pr-2">
                {topologies.map(topo => (
                    <TopologyCard 
                        key={topo.id} 
                        topo={topo} 
                        onClick={() => setActiveTopology(topo)} 
                    />
                ))}
            </div>

            <AnimatePresence>
                {isCreateModalOpen && (
                    <CreateTopologyModal 
                        onClose={() => setIsCreateModalOpen(false)}
                        onCreate={handleCreateTopology}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}