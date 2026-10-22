/**
 * 下载管理页面
 *
 * 管理插件下载、更新任务
 */

import React, { useState, useMemo } from "react";
import {
  Download,
  Pause,
  Play,
  X,
  Trash2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  FolderOpen,
  Package,
  Clock,
  HardDrive,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

type DownloadStatus = 'pending' | 'downloading' | 'paused' | 'completed' | 'failed' | 'installing';

interface DownloadTask {
  id: string;
  name: string;
  version: string;
  size: string;
  status: DownloadStatus;
  progress: number;
  speed: string;
  eta: string;
  category: string;
  icon?: string;
  downloadedSize: string;
  error?: string;
}

// 模拟下载任务
const mockDownloads: DownloadTask[] = [
  {
    id: 'dl-001',
    name: 'VS Code 插件包',
    version: '1.2.0',
    size: '45.6 MB',
    status: 'downloading',
    progress: 67,
    speed: '3.2 MB/s',
    eta: '8s',
    category: 'editor',
    downloadedSize: '30.5 MB',
  },
  {
    id: 'dl-002',
    name: 'Node.js 运行时',
    version: '20.0.0',
    size: '32.1 MB',
    status: 'paused',
    progress: 45,
    speed: '0',
    eta: '--',
    category: 'runtime',
    downloadedSize: '14.4 MB',
  },
  {
    id: 'dl-003',
    name: 'Docker Compose',
    version: '2.24.0',
    size: '58.2 MB',
    status: 'completed',
    progress: 100,
    speed: '0',
    eta: '--',
    category: 'system',
    downloadedSize: '58.2 MB',
  },
  {
    id: 'dl-004',
    name: 'Python 3.11',
    version: '3.11.9',
    size: '24.5 MB',
    status: 'failed',
    progress: 30,
    speed: '0',
    eta: '--',
    category: 'runtime',
    downloadedSize: '7.3 MB',
    error: '网络连接超时',
  },
  {
    id: 'dl-005',
    name: 'Redis 客户端',
    version: '1.0.0',
    size: '12.8 MB',
    status: 'installing',
    progress: 100,
    speed: '0',
    eta: '--',
    category: 'database',
    downloadedSize: '12.8 MB',
  },
];

type FilterType = 'all' | 'downloading' | 'completed' | 'failed';

export const DownloadsView: React.FC = () => {
  const [downloads, setDownloads] = useState<DownloadTask[]>(mockDownloads);
  const [filter, setFilter] = useState<FilterType>('all');

  // 过滤后的任务
  const filteredDownloads = useMemo(() => {
    if (filter === 'all') return downloads;
    return downloads.filter(d => d.status === filter);
  }, [downloads, filter]);

  // 统计
  const stats = useMemo(() => ({
    total: downloads.length,
    downloading: downloads.filter(d => d.status === 'downloading').length,
    completed: downloads.filter(d => d.status === 'completed' || d.status === 'installing').length,
    failed: downloads.filter(d => d.status === 'failed').length,
  }), [downloads]);

  // 操作处理
  const handleAction = (id: string, action: 'pause' | 'resume' | 'cancel' | 'retry' | 'delete' | 'install') => {
    switch (action) {
      case 'pause':
        setDownloads(downloads.map(d => d.id === id ? { ...d, status: 'paused' as DownloadStatus } : d));
        toast.success('下载已暂停');
        break;
      case 'resume':
        setDownloads(downloads.map(d => d.id === id ? { ...d, status: 'downloading' as DownloadStatus } : d));
        toast.success('下载继续');
        break;
      case 'cancel':
        if (confirm('确定要取消这个下载吗？')) {
          setDownloads(downloads.filter(d => d.id !== id));
          toast.success('下载已取消');
        }
        break;
      case 'delete':
        setDownloads(downloads.filter(d => d.id !== id));
        toast.success('已删除');
        break;
      case 'retry':
        setDownloads(downloads.map(d => d.id === id ? { ...d, status: 'downloading' as DownloadStatus, progress: 0, error: undefined } : d));
        toast.success('重新开始下载');
        break;
      case 'install':
        setDownloads(downloads.map(d => d.id === id ? { ...d, status: 'installing' as DownloadStatus } : d));
        toast.success('开始安装');
        break;
    }
  };

  // 批量操作
  const handleClearCompleted = () => {
    setDownloads(downloads.filter(d => d.status !== 'completed' && d.status !== 'installing'));
    toast.success('已清除完成的任务');
  };

  // 获取状态配置
  const getStatusConfig = (status: DownloadStatus) => {
    switch (status) {
      case 'downloading':
        return {
          icon: Download,
          color: 'text-blue-500',
          bg: 'bg-blue-500/10',
          label: '下载中'
        };
      case 'paused':
        return {
          icon: Pause,
          color: 'text-amber-500',
          bg: 'bg-amber-500/10',
          label: '已暂停'
        };
      case 'completed':
        return {
          icon: CheckCircle2,
          color: 'text-emerald-500',
          bg: 'bg-emerald-500/10',
          label: '已完成'
        };
      case 'failed':
        return {
          icon: AlertCircle,
          color: 'text-red-500',
          bg: 'bg-red-500/10',
          label: '下载失败'
        };
      case 'installing':
        return {
          icon: RefreshCw,
          color: 'text-purple-500',
          bg: 'bg-purple-500/10',
          label: '安装中',
          spin: true
        };
      default:
        return {
          icon: Clock,
          color: 'text-[var(--c-500)]',
          bg: 'bg-[var(--c-800)]',
          label: '等待中'
        };
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">下载管理</h2>
          <p className="text-[var(--c-500)] text-sm">管理插件下载和安装任务</p>
        </div>
        <button
          onClick={handleClearCompleted}
          className="px-4 py-2 bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
        >
          <Trash2 size={16} />
          清除已完成
        </button>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[var(--c-500)] text-sm">全部</span>
            <Download size={16} className="text-[var(--c-500)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--c-100)]">{stats.total}</div>
        </div>
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[var(--c-500)] text-sm">下载中</span>
            <Download size={16} className="text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-[var(--c-100)]">{stats.downloading}</div>
        </div>
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[var(--c-500)] text-sm">已完成</span>
            <CheckCircle2 size={16} className="text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-[var(--c-100)]">{stats.completed}</div>
        </div>
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[var(--c-500)] text-sm">失败</span>
            <AlertCircle size={16} className="text-red-500" />
          </div>
          <div className="text-2xl font-bold text-[var(--c-100)]">{stats.failed}</div>
        </div>
      </div>

      {/* 过滤器 */}
      <div className="flex items-center gap-2">
        {(['all', 'downloading', 'completed', 'failed'] as FilterType[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              filter === f
                ? 'bg-[var(--c-100)] text-[var(--c-950)]'
                : 'bg-[var(--c-800)] text-[var(--c-400)] hover:bg-[var(--c-700)] hover:text-[var(--c-200)]'
            }`}
          >
            {f === 'all' && '全部'}
            {f === 'downloading' && '下载中'}
            {f === 'completed' && '已完成'}
            {f === 'failed' && '失败'}
          </button>
        ))}
      </div>

      {/* 下载列表 */}
      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {filteredDownloads.length === 0 ? (
            <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-12 text-center">
              <Package size={48} className="mx-auto text-[var(--c-700)] mb-4" />
              <p className="text-[var(--c-500)]">暂无下载任务</p>
            </div>
          ) : (
            filteredDownloads.map((task) => {
              const statusConfig = getStatusConfig(task.status);
              const isCompleted = task.status === 'completed' || task.status === 'installing';
              const canInstall = task.status === 'completed';

              return (
                <motion.div
                  key={task.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.2 }}
                  className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4 hover:border-[var(--c-700)] transition-colors"
                >
                  <div className="flex items-center gap-4">
                    {/* 图标 */}
                    <div className="w-12 h-12 rounded-lg bg-[var(--c-800)] flex items-center justify-center flex-shrink-0">
                      <Package size={24} className="text-[var(--c-500)]" />
                    </div>

                    {/* 信息 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="text-sm font-semibold text-[var(--c-100)]">{task.name}</h4>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${statusConfig.bg} ${statusConfig.color} flex items-center gap-1`}>
                          <statusConfig.icon size={10} className={statusConfig.spin ? 'animate-spin' : ''} />
                          {statusConfig.label}
                        </span>
                        <span className="text-xs text-[var(--c-600)]">v{task.version}</span>
                      </div>

                      {/* 进度条 */}
                      {task.status !== 'failed' && task.status !== 'installing' && (
                        <div className="mb-1">
                          <div className="flex items-center justify-between text-xs text-[var(--c-500)] mb-1">
                            <span>{task.downloadedSize} / {task.size}</span>
                            <span>{task.progress}%</span>
                          </div>
                          <div className="h-1.5 bg-[var(--c-800)] rounded-full overflow-hidden">
                            <motion.div
                              className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                              initial={{ width: 0 }}
                              animate={{ width: `${task.progress}%` }}
                              transition={{ duration: 0.3 }}
                            />
                          </div>
                        </div>
                      )}

                      {/* 错误信息 */}
                      {task.error && (
                        <p className="text-xs text-red-400">{task.error}</p>
                      )}

                      {/* 速度和ETA */}
                      {task.status === 'downloading' && (
                        <div className="flex items-center gap-4 text-xs text-[var(--c-500)]">
                          <span className="flex items-center gap-1">
                            <Download size={12} />
                            {task.speed}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock size={12} />
                            {task.eta}
                          </span>
                          <span>{task.category}</span>
                        </div>
                      )}

                      {task.status === 'installing' && (
                        <div className="flex items-center gap-2 text-xs text-purple-400">
                          <RefreshCw size={12} className="animate-spin" />
                          正在安装到系统...
                        </div>
                      )}
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex items-center gap-2">
                      {task.status === 'downloading' && (
                        <button
                          onClick={() => handleAction(task.id, 'pause')}
                          className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors"
                          title="暂停"
                        >
                          <Pause size={16} />
                        </button>
                      )}
                      {task.status === 'paused' && (
                        <button
                          onClick={() => handleAction(task.id, 'resume')}
                          className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors"
                          title="继续"
                        >
                          <Play size={16} />
                        </button>
                      )}
                      {task.status === 'failed' && (
                        <button
                          onClick={() => handleAction(task.id, 'retry')}
                          className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors"
                          title="重试"
                        >
                          <RefreshCw size={16} />
                        </button>
                      )}
                      {canInstall && (
                        <button
                          onClick={() => handleAction(task.id, 'install')}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-medium transition-colors"
                        >
                          安装
                        </button>
                      )}
                      <button
                        onClick={() => handleAction(task.id, 'cancel')}
                        className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-red-400 transition-colors"
                        title={isCompleted ? '删除' : '取消'}
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                </motion.div>
              );
            })
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default DownloadsView;
