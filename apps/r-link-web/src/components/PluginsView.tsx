/**
 * 插件管理视图组件
 * 使用后端API获取插件数据
 */

import React, { useState, useMemo } from "react";
import {
  Plus, Terminal, Server, Zap, Archive, ShieldCheck, Star, Download,
  Puzzle, Settings, MoreHorizontal, Play, Square, RotateCw,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  usePlugins,
  usePluginActions
} from "@/api/hooks";
import { PluginDetailModal } from "./PluginDetailModal";
import type { Plugin } from "@/api/types";

// 扩展插件类型用于UI显示
interface PluginUI extends Plugin {
  rating?: number;
  downloads?: string;
  verified?: boolean;
  features?: string[];
  longDescription?: string;
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const config = {
    running: { label: '运行中', className: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' },
    stopped: { label: '已停止', className: 'bg-[var(--c-500-5)] text-[var(--c-500)] border-[var(--c-500-20)]' },
    error: { label: '错误', className: 'bg-red-500/10 text-red-500 border-red-500/20' },
  };

  const { label, className } = config[status as keyof typeof config] || config.stopped;

  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${className}`}>
      {label}
    </span>
  );
};

const PluginCard: React.FC<{
  plugin: PluginUI;
  onClick: () => void;
  onStatusToggle: (plugin: PluginUI) => Promise<void>;
  loading?: boolean;
}> = ({ plugin, onClick, onStatusToggle, loading }) => {
  const Icon = plugin.icon ? (() => null) : Puzzle; // 简化处理，实际应映射图标

  const handleStatusToggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await onStatusToggle(plugin);
  };

  return (
    <div
      onClick={onClick}
      className="group bg-[var(--c-900)] border border-[var(--c-800)] hover:border-[var(--c-700)] hover:bg-[var(--c-900-50)] rounded-xl p-5 cursor-pointer transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="w-12 h-12 rounded-lg bg-[var(--c-800)] flex items-center justify-center text-[var(--c-200)] group-hover:scale-110 transition-transform duration-300">
          <Puzzle size={24} />
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusBadge status={plugin.status?.status || 'stopped'} />
        </div>
      </div>

      <h3 className="text-[var(--c-100)] font-bold mb-1 flex items-center gap-1.5">
        {plugin.name}
        {plugin.verified && <ShieldCheck size={14} className="text-blue-500" />}
      </h3>
      <p className="text-xs text-[var(--c-500)] line-clamp-2 h-8 mb-4 leading-relaxed">
        {plugin.description}
      </p>

      <div className="flex items-center justify-between text-[10px] text-[var(--c-600)] border-t border-[var(--c-800-50)] pt-3">
        <div className="flex items-center gap-3">
          <span className="font-mono">v{plugin.version}</span>
          {plugin.author && <span>by {plugin.author}</span>}
        </div>
        {plugin.status?.status === 'running' && plugin.status?.cpu_usage !== undefined && (
          <span className="text-[var(--c-400)]">{plugin.status.cpu_usage.toFixed(1)}% CPU</span>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="mt-4 flex gap-2">
        {plugin.status?.status === 'running' ? (
          <>
            <button
              onClick={handleStatusToggle}
              disabled={loading}
              className="flex-1 px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-medium transition-colors flex items-center justify-center gap-1"
            >
              <Square size={12} /> 停止
            </button>
            <button
              onClick={handleStatusToggle}
              disabled={loading}
              className="px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 text-xs font-medium transition-colors"
            >
              <RotateCw size={12} />
            </button>
          </>
        ) : (
          <button
            onClick={handleStatusToggle}
            disabled={loading}
            className="w-full px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-medium transition-colors flex items-center justify-center gap-1"
          >
            <Play size={12} /> 启动
          </button>
        )}
      </div>
    </div>
  );
};

export const PluginsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState("installed");
  const [selectedPlugin, setSelectedPlugin] = useState<PluginUI | null>(null);

  // 使用 API Hooks
  const { data: plugins = [], loading, error, refetch } = usePlugins();
  const { start, stop, restart, loading: actionLoading } = usePluginActions();

  // 分类插件
  const installedPlugins = useMemo(() => (plugins || []).filter(p => p), [plugins]);

  const handleStatusToggle = async (plugin: PluginUI) => {
    try {
      if (plugin.status?.status === 'running') {
        await stop(plugin.name);
        toast.success(`已停止 ${plugin.name}`);
      } else {
        await start(plugin.name);
        toast.success(`已启动 ${plugin.name}`);
      }
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleRestart = async (plugin: PluginUI) => {
    try {
      await restart(plugin.name);
      toast.success(`已重启 ${plugin.name}`);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-[var(--c-500)] space-y-4">
        <div className="w-16 h-16 rounded-full bg-[var(--c-800-50)] flex items-center justify-center">
          <Settings size={32} className="opacity-20" />
        </div>
        <p className="text-sm">无法连接到后端服务</p>
        <p className="text-xs text-[var(--c-600)]">请确保 R-Link Server 正在运行</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-[var(--c-800)] text-[var(--c-200)] rounded-lg text-sm hover:bg-[var(--c-700)] transition-colors"
        >
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">插件管理</h2>
          <p className="text-[var(--c-500)] text-sm">管理和控制系统插件</p>
        </div>
        <div className="flex gap-2 bg-[var(--c-900)] p-1 rounded-lg border border-[var(--c-800)]">
          <button
            onClick={() => setActiveTab("installed")}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "installed"
                ? "bg-[var(--c-800)] text-[var(--c-100)] shadow-sm"
                : "text-[var(--c-500)] hover:text-[var(--c-300)]"
            }`}
          >
            已安装 ({installedPlugins.length})
          </button>
          <button
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "market"
                ? "bg-[var(--c-800)] text-[var(--c-100)] shadow-sm"
                : "text-[var(--c-500)] hover:text-[var(--c-300)]"
            }`}
          >
            插件市场
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-pulse text-[var(--c-500)]">加载中...</div>
        </div>
      ) : installedPlugins.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-[var(--c-500)] space-y-4">
          <div className="w-16 h-16 rounded-full bg-[var(--c-800-50)] flex items-center justify-center">
            <Puzzle size={32} className="opacity-20" />
          </div>
          <p className="text-sm">暂无已安装的插件</p>
          <p className="text-xs text-[var(--c-600)]">请将插件放入 plugins 目录后重启服务</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {installedPlugins.map((plugin) => (
            <PluginCard
              key={plugin.name}
              plugin={plugin as PluginUI}
              onClick={() => setSelectedPlugin(plugin as PluginUI)}
              onStatusToggle={handleStatusToggle}
              loading={actionLoading}
            />
          ))}
        </div>
      )}

      <AnimatePresence>
        {selectedPlugin && (
          <PluginDetailModal
            plugin={{
              ...selectedPlugin,
              icon: Puzzle,
              features: selectedPlugin.features || [],
              rating: selectedPlugin.rating || 4.5,
              downloads: selectedPlugin.downloads || '0',
              verified: selectedPlugin.verified || false,
            }}
            onClose={() => setSelectedPlugin(null)}
            onInstall={() => {
              toast.success(`已开始安装 ${selectedPlugin.name}`);
              setSelectedPlugin(null);
            }}
            onUninstall={() => {
              toast.success(`已卸载 ${selectedPlugin.name}`);
              setSelectedPlugin(null);
              refetch();
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default PluginsView;
