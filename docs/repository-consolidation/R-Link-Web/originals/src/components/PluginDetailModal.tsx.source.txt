import React, { useState } from "react";
import { motion } from "framer-motion";
import { 
  X, 
  Download, 
  Trash2, 
  Settings, 
  FileText, 
  Star, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  Puzzle,
  ExternalLink,
  ShieldCheck,
  Zap
} from "lucide-react";

const PluginDetailModal = ({ plugin, onClose, onInstall, onUninstall }) => {
  const [activeTab, setActiveTab] = useState("overview");

  if (!plugin) return null;

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
        className="w-full max-w-2xl bg-[var(--c-950-85)] backdrop-blur-2xl border border-[var(--c-800)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[600px]"
      >
        {/* Header */}
        <div className="px-6 py-6 border-b border-[var(--c-800-50)] flex items-start justify-between shrink-0 bg-[var(--c-900-30)]">
           <div className="flex gap-5">
              <div className="w-20 h-20 rounded-xl bg-[var(--c-800)] border border-[var(--c-700)] flex items-center justify-center shadow-lg">
                 {plugin.icon ? <plugin.icon size={40} className="text-[var(--c-200)]" /> : <Puzzle size={40} className="text-[var(--c-200)]" />}
              </div>
              <div>
                 <h2 className="text-xl font-bold text-[var(--c-100)] flex items-center gap-2">
                    {plugin.name}
                    {plugin.verified && <ShieldCheck size={16} className="text-blue-400" title="官方认证" />}
                 </h2>
                 <p className="text-sm text-[var(--c-400)] mt-1 max-w-md leading-relaxed">{plugin.description}</p>
                 <div className="flex items-center gap-4 text-xs text-[var(--c-500)] mt-3">
                    <span className="flex items-center gap-1"><Star size={12} className="text-amber-400 fill-amber-400" /> {plugin.rating}</span>
                    <span className="flex items-center gap-1"><Download size={12} /> {plugin.downloads}</span>
                    <span className="bg-[var(--c-800)] px-2 py-0.5 rounded text-[var(--c-400)]">v{plugin.version}</span>
                 </div>
              </div>
           </div>
           <button onClick={onClose} className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors">
              <X size={20} />
           </button>
        </div>

        {/* Action Bar */}
        <div className="px-6 py-3 border-b border-[var(--c-800-50)] flex items-center justify-between bg-[var(--c-900-50)]">
           <div className="flex gap-6">
              <button 
                onClick={() => setActiveTab("overview")}
                className={`text-sm font-medium transition-colors ${activeTab === "overview" ? "text-[var(--c-100)]" : "text-[var(--c-500)] hover:text-[var(--c-300)]"}`}
              >
                概览
              </button>
              <button 
                onClick={() => setActiveTab("config")}
                className={`text-sm font-medium transition-colors ${activeTab === "config" ? "text-[var(--c-100)]" : "text-[var(--c-500)] hover:text-[var(--c-300)]"}`}
              >
                配置
              </button>
              <button 
                onClick={() => setActiveTab("logs")}
                className={`text-sm font-medium transition-colors ${activeTab === "logs" ? "text-[var(--c-100)]" : "text-[var(--c-500)] hover:text-[var(--c-300)]"}`}
              >
                更新日志
              </button>
           </div>
           
           <div>
              {plugin.status === 'installed' ? (
                  <div className="flex gap-2">
                      <button 
                        onClick={() => onUninstall && onUninstall(plugin)}
                        className="px-4 py-1.5 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 text-xs font-medium transition-colors flex items-center gap-2"
                      >
                         <Trash2 size={14} /> 卸载
                      </button>
                      <button className="px-4 py-1.5 rounded-lg bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] text-xs font-medium transition-colors flex items-center gap-2">
                         <Settings size={14} /> 设置
                      </button>
                  </div>
              ) : (
                  <button 
                    onClick={() => onInstall && onInstall(plugin)}
                    className="px-6 py-1.5 rounded-lg bg-[var(--c-100)] hover:bg-[var(--c-white)] text-[var(--c-900)] text-xs font-bold transition-colors flex items-center gap-2 shadow-lg shadow-white/5"
                  >
                     <Download size={14} /> 安装插件
                  </button>
              )}
           </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-card">
           {activeTab === 'overview' && (
              <div className="space-y-6">
                 <div className="space-y-3">
                    <h3 className="text-sm font-bold text-[var(--c-200)] flex items-center gap-2">
                        <Zap size={16} /> 功能特性
                    </h3>
                    <ul className="grid grid-cols-2 gap-2">
                        {plugin.features?.map((feature, i) => (
                            <li key={i} className="flex items-center gap-2 text-xs text-[var(--c-400)] bg-[var(--c-900-50)] p-2 rounded-lg border border-[var(--c-800-50)]">
                                <CheckCircle2 size={14} className="text-emerald-500" />
                                {feature}
                            </li>
                        )) || <li className="text-xs text-[var(--c-500)]">暂无详细特性描述</li>}
                    </ul>
                 </div>
                 
                 <div className="space-y-3">
                    <h3 className="text-sm font-bold text-[var(--c-200)] flex items-center gap-2">
                        <FileText size={16} /> 简介
                    </h3>
                    <div className="text-xs text-[var(--c-400)] leading-relaxed space-y-2">
                        <p>{plugin.longDescription || "这是一个功能强大的插件，可以帮助您更好地管理网络设备。它提供了实时监控、自动报警和数据分析功能。"}</p>
                    </div>
                 </div>

                 <div className="space-y-3">
                    <h3 className="text-sm font-bold text-[var(--c-200)] flex items-center gap-2">
                        <Clock size={16} /> 信息
                    </h3>
                    <div className="grid grid-cols-2 gap-4 text-xs">
                        <div className="flex justify-between py-2 border-b border-[var(--c-800-50)]">
                            <span className="text-[var(--c-500)]">发布日期</span>
                            <span className="text-[var(--c-300)]">2023-10-01</span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-[var(--c-800-50)]">
                            <span className="text-[var(--c-500)]">最后更新</span>
                            <span className="text-[var(--c-300)]">2023-10-25</span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-[var(--c-800-50)]">
                            <span className="text-[var(--c-500)]">开发者</span>
                            <span className="text-[var(--c-300)] flex items-center gap-1 text-blue-400 cursor-pointer hover:underline">
                                {plugin.author} <ExternalLink size={10} />
                            </span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-[var(--c-800-50)]">
                            <span className="text-[var(--c-500)]">许可协议</span>
                            <span className="text-[var(--c-300)]">MIT</span>
                        </div>
                    </div>
                 </div>
              </div>
           )}

           {activeTab === 'config' && (
              <div className="flex flex-col items-center justify-center h-full text-[var(--c-500)] space-y-4 min-h-[200px]">
                  <Settings size={32} className="opacity-20" />
                  <p className="text-sm">安装后可在此处配置插件参数</p>
              </div>
           )}

           {activeTab === 'logs' && (
              <div className="space-y-4">
                  {[
                      { v: "1.2.0", date: "2023-10-25", content: "修复了已知的内存泄漏问题；优化了数据同步速度。" },
                      { v: "1.1.0", date: "2023-10-10", content: "新增了暗黑模式支持；改进了用户界面交互。" },
                      { v: "1.0.0", date: "2023-10-01", content: "首次发布。" }
                  ].map((log, i) => (
                      <div key={i} className="flex gap-4">
                          <div className="flex flex-col items-center">
                              <div className="w-2 h-2 rounded-full bg-[var(--c-700)] mt-2" />
                              {i !== 2 && <div className="w-px h-full bg-[var(--c-800)] my-1" />}
                          </div>
                          <div className="pb-4">
                              <div className="flex items-center gap-3 mb-1">
                                  <span className="text-sm font-bold text-[var(--c-200)]">v{log.v}</span>
                                  <span className="text-xs text-[var(--c-500)]">{log.date}</span>
                              </div>
                              <p className="text-xs text-[var(--c-400)] leading-relaxed">{log.content}</p>
                          </div>
                      </div>
                  ))}
              </div>
           )}
        </div>
      </motion.div>
    </div>
  );
};

export { PluginDetailModal };
