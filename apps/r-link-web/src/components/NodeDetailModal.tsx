import React, { useState } from "react";
import {
  Activity,
  Server,
  Monitor,
  HardDrive,
  Folder,
  Cloud,
  Wifi,
  Laptop,
  Cpu,
  Terminal,
  X,
  Shield,
  Zap,
  Puzzle,
  Power,
  Network,
  RefreshCw,
  Signal,
  Lock,
  Globe,
  Database,
  Box,
  Plus
} from "lucide-react";
import { motion } from "framer-motion";

const NodeDetailModal = ({ node, onClose }) => {
  // Mock data for demonstration
  const plugins = [
    { id: 'nginx', name: 'Nginx', icon: Globe, active: true },
    { id: 'docker', name: 'Docker', icon: Box, active: true },
    { id: 'firewall', name: 'Firewall', icon: Shield, active: true },
    { id: 'db', name: 'Database', icon: Database, active: false },
    { id: 'monitor', name: 'Monitor', icon: Activity, active: false },
  ];

  const quickActions = [
    { id: 'remote', name: '远程控制', icon: Monitor, color: 'text-blue-400' },
    { id: 'ssh', name: 'SSH 连接', icon: Terminal, color: 'text-emerald-400' },
    { id: 'files', name: '文件管理', icon: Folder, color: 'text-amber-400' },
    { id: 'net', name: '网络测试', icon: Signal, color: 'text-violet-400' },
    { id: 'restart', name: '重启系统', icon: RefreshCw, color: 'text-red-400' },
  ];

  const getNodeIcon = (type) => {
    switch(type) {
        case 'cloud': return Cloud;
        case 'router': return Wifi;
        case 'switch': return Server;
        case 'desktop': return Monitor;
        case 'laptop': return Laptop;
        case 'server': return HardDrive;
        case 'auth': return Shield;
        case 'plugin': return Puzzle;
        default: return Server;
    }
  };

  const NodeIcon = getNodeIcon(node.type);

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-8 backdrop-blur-sm" 
      style={{ backgroundColor: 'var(--c-modal-overlay)' }}
      onClick={onClose}
    >
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-4xl bg-[var(--c-950-85)] backdrop-blur-2xl border border-[var(--c-800)] rounded-3xl shadow-2xl overflow-hidden flex flex-col h-[420px]"
      >
        {/* Top Section: Node Info & Plugins */}
        <div className="flex-1 border-b border-[var(--c-800-50)] flex min-h-0">
            {/* Top Left: Node Information */}
            <div className="w-1/3 p-6 border-r border-[var(--c-800-50)] flex flex-col relative bg-[var(--c-900-30)]">
                <button 
                    onClick={onClose} 
                    className="absolute top-4 left-4 p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors"
                >
                    <X size={18} />
                </button>

                <div className="flex-1 flex flex-col items-center justify-center text-center mt-4">
                    <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 shadow-xl ${
                        node.status === 'active' ? 'bg-[var(--c-800)] text-[var(--c-100)]' : 'bg-amber-900/20 text-amber-500'
                    }`}>
                        <NodeIcon size={32} strokeWidth={1.5} />
                    </div>
                    <h2 className="text-xl font-bold text-[var(--c-100)] mb-1">{node.label}</h2>
                    <span className="text-xs text-[var(--c-500)] bg-[var(--c-800-50)] px-2 py-0.5 rounded border border-[var(--c-800)] mb-4 font-mono uppercase">
                        {node.type} • {node.id.slice(-6)}
                    </span>
                    
                    <div className="flex items-center gap-2 text-xs font-medium">
                        <span className={`w-2 h-2 rounded-full ${node.status === 'active' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                        <span className={node.status === 'active' ? 'text-emerald-500' : 'text-amber-500'}>
                            {node.status === 'active' ? '运行正常' : '异常状态'}
                        </span>
                    </div>
                </div>

                <div className="space-y-2 mt-auto pt-4 border-t border-[var(--c-800-50)]">
                    <div className="flex justify-between text-xs">
                        <span className="text-[var(--c-500)]">IP Address</span>
                        <span className="text-[var(--c-300)] font-mono">{node.ip || '192.168.1.100'}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                        <span className="text-[var(--c-500)]">Uptime</span>
                        <span className="text-[var(--c-300)] font-mono">14d 2h 15m</span>
                    </div>
                </div>
            </div>

            {/* Top Right: Installed Plugins */}
            <div className="flex-1 p-6 flex flex-col">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-[var(--c-200)] flex items-center gap-2">
                        <Puzzle size={16} /> 已安装插件
                    </h3>
                    <span className="text-xs text-[var(--c-500)]">{plugins.filter(p => p.active).length} Active</span>
                </div>
                
                <div className="grid grid-cols-4 gap-4 overflow-hidden">
                    {plugins.map(plugin => (
                        <button key={plugin.id} className="group relative flex flex-col items-center gap-2 p-3 rounded-xl bg-[var(--c-900-50)] border border-[var(--c-800)] hover:border-[var(--c-600)] hover:bg-[var(--c-800)] transition-all">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${plugin.active ? 'text-[var(--c-100)] bg-[var(--c-700-30)]' : 'text-[var(--c-600)] bg-[var(--c-900)]'}`}>
                                <plugin.icon size={20} />
                            </div>
                            <span className="text-xs text-[var(--c-400)] group-hover:text-[var(--c-200)] font-medium">{plugin.name}</span>
                            {plugin.active && (
                                <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-emerald-500 rounded-full shadow-[0_0_4px_rgba(16,185,129,0.5)]" />
                            )}
                        </button>
                    ))}
                    
                    <button className="flex flex-col items-center justify-center gap-2 p-3 rounded-xl border border-dashed border-[var(--c-700)] hover:border-[var(--c-500)] hover:bg-[var(--c-800-30)] transition-all group aspect-square">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--c-600)] group-hover:text-[var(--c-400)]">
                            <Plus size={20} />
                        </div>
                        <span className="text-xs text-[var(--c-500)] group-hover:text-[var(--c-300)]">Add</span>
                    </button>
                </div>
            </div>
        </div>

        {/* Bottom Section: Common Functions */}
        <div className="h-20 bg-[var(--c-900-30)] px-6 flex items-center shrink-0">
             <div className="text-sm font-bold text-[var(--c-500)] uppercase tracking-wider w-24 shrink-0 flex items-center gap-2">
                <Zap size={14} /> 常用功能
             </div>
             <div className="flex-1 flex gap-3 overflow-hidden">
                {quickActions.map(action => (
                    <button 
                        key={action.id}
                        className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-[var(--c-900)] border border-[var(--c-800)] hover:border-[var(--c-600)] hover:bg-[var(--c-800)] hover:-translate-y-0.5 transition-all shadow-sm"
                    >
                        <action.icon size={16} className={action.color} />
                        <span className="text-xs font-medium text-[var(--c-300)] whitespace-nowrap">{action.name}</span>
                    </button>
                ))}
             </div>
        </div>
      </motion.div>
    </div>
  );
};

export { NodeDetailModal };
