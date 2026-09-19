/**
 * 个人中心页面
 *
 * 包含用户信息、已安装插件管理、账户设置等功能
 */

import React, { useState, useMemo } from "react";
import {
  User,
  Mail,
  Shield,
  Bell,
  Palette,
  Globe,
  Puzzle,
  Trash2,
  Power,
  Settings,
  CheckCircle2,
  AlertCircle,
  Play,
  Pause,
  RotateCcw,
  Clock,
  HardDrive,
  Download,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

// 插件状态类型
type PluginStatus = 'running' | 'stopped' | 'error' | 'installing' | 'updating';

interface InstalledPlugin {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  icon?: string;
  status: PluginStatus;
  category: string;
  installedAt: string;
  size: string;
  path: string;
}

interface UserInfo {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
  role: 'admin' | 'user' | 'guest';
  joinedAt: string;
  lastLogin: string;
}

// 模拟已安装插件数据
const mockInstalledPlugins: InstalledPlugin[] = [
  {
    id: 'docker-manager',
    name: 'Docker 管理器',
    version: '1.0.0',
    description: 'Docker 容器管理插件 - 支持容器、镜像、网络和卷的管理',
    author: 'R-Link',
    status: 'running',
    category: 'system',
    installedAt: '2026-01-15',
    size: '2.4 MB',
    path: 'builtin/docker_manager',
  },
  {
    id: 'software-installer',
    name: '软件安装器',
    version: '1.0.0',
    description: '软件自动安装插件 - 支持 Docker、Git、Node.js 等软件的检测和安装',
    author: 'R-Link',
    status: 'running',
    category: 'system',
    installedAt: '2026-01-15',
    size: '1.8 MB',
    path: 'builtin/software_installer',
  },
  {
    id: 'nginx-plugin',
    name: 'Nginx 反向代理',
    version: '1.0.0',
    description: 'Nginx 反向代理服务，用于管理 HTTP/HTTPS 请求转发',
    author: 'R-Link Team',
    status: 'stopped',
    category: 'network',
    installedAt: '2026-01-10',
    size: '12.5 MB',
    path: 'builtin/nginx-plugin',
  },
  {
    id: 'hello-plugin',
    name: 'Hello 测试插件',
    version: '1.0.0',
    description: '一个简单的测试插件，演示插件系统的基本功能',
    author: 'R-Link Team',
    status: 'stopped',
    category: 'general',
    installedAt: '2026-01-08',
    size: '256 KB',
    path: 'plugins/hello-plugin',
  },
];

// 模拟用户信息
const mockUserInfo: UserInfo = {
  id: 'user-001',
  email: 'admin@r-link.dev',
  name: 'R-Link 管理员',
  avatar: 'RL',
  role: 'admin',
  joinedAt: '2025-12-01',
  lastLogin: new Date().toISOString(),
};

type ProfileTab = 'overview' | 'plugins' | 'settings' | 'security';

const tabConfig = [
  { id: 'overview' as ProfileTab, label: '概览', icon: User },
  { id: 'plugins' as ProfileTab, label: '我的插件', icon: Puzzle },
  { id: 'settings' as ProfileTab, label: '设置', icon: Settings },
  { id: 'security' as ProfileTab, label: '安全', icon: Shield },
];

export const ProfileView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ProfileTab>('overview');
  const [plugins, setPlugins] = useState<InstalledPlugin[]>(mockInstalledPlugins);
  const [selectedPlugins, setSelectedPlugins] = useState<Set<string>>(new Set());

  // 插件操作
  const handlePluginAction = async (pluginId: string, action: 'start' | 'stop' | 'restart' | 'uninstall') => {
    const plugin = plugins.find(p => p.id === pluginId);
    if (!plugin) return;

    switch (action) {
      case 'start':
        setPlugins(plugins.map(p => p.id === pluginId ? { ...p, status: 'running' } : p));
        toast.success(`已启动 ${plugin.name}`);
        break;
      case 'stop':
        setPlugins(plugins.map(p => p.id === pluginId ? { ...p, status: 'stopped' } : p));
        toast.success(`已停止 ${plugin.name}`);
        break;
      case 'restart':
        setPlugins(plugins.map(p => p.id === pluginId ? { ...p, status: 'running' } : p));
        toast.success(`已重启 ${plugin.name}`);
        break;
      case 'uninstall':
        if (confirm(`确定要卸载 ${plugin.name} 吗？`)) {
          setPlugins(plugins.filter(p => p.id !== pluginId));
          toast.success(`已卸载 ${plugin.name}`);
        }
        break;
    }
  };

  // 批量操作
  const handleBatchAction = async (action: 'start' | 'stop' | 'uninstall') => {
    for (const pluginId of selectedPlugins) {
      await handlePluginAction(pluginId, action);
    }
    setSelectedPlugins(new Set());
  };

  // 获取状态图标和颜色
  const getStatusConfig = (status: PluginStatus) => {
    switch (status) {
      case 'running':
        return { icon: Play, color: 'text-emerald-500', bg: 'bg-emerald-500/10', label: '运行中' };
      case 'stopped':
        return { icon: Pause, color: 'text-[var(--c-500)]', bg: 'bg-[var(--c-800)]', label: '已停止' };
      case 'error':
        return { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-500/10', label: '错误' };
      case 'installing':
        return { icon: Download, color: 'text-blue-500', bg: 'bg-blue-500/10', label: '安装中' };
      case 'updating':
        return { icon: RotateCcw, color: 'text-amber-500', bg: 'bg-amber-500/10', label: '更新中' };
      default:
        return { icon: Clock, color: 'text-[var(--c-500)]', bg: 'bg-[var(--c-800)]', label: '未知' };
    }
  };

  // 统计信息
  const stats = useMemo(() => ({
    total: plugins.length,
    running: plugins.filter(p => p.status === 'running').length,
    stopped: plugins.filter(p => p.status === 'stopped').length,
    builtin: plugins.filter(p => p.path.startsWith('builtin/')).length,
    user: plugins.filter(p => p.path.startsWith('plugins/')).length,
  }), [plugins]);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">个人中心</h2>
          <p className="text-[var(--c-500)] text-sm">管理您的账户和已安装的插件</p>
        </div>
      </div>

      {/* Tab 导航 */}
      <div className="flex border-b border-[var(--c-800)]">
        {tabConfig.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors relative ${
              activeTab === tab.id
                ? 'text-[var(--c-100)]'
                : 'text-[var(--c-500)] hover:text-[var(--c-300)]'
            }`}
          >
            <tab.icon size={16} />
            {tab.label}
            {activeTab === tab.id && (
              <motion.div
                layoutId="profile-tab"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"
                initial={false}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            )}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      <AnimatePresence mode="wait">
        {activeTab === 'overview' && (
          <motion.div
            key="overview"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            {/* 用户信息卡片 */}
            <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-2xl overflow-hidden">
              <div className="h-24 bg-gradient-to-r from-blue-600 to-purple-600" />
              <div className="px-6 pb-6 -mt-12">
                <div className="flex items-end gap-4 mb-4">
                  <div className="w-20 h-20 rounded-2xl bg-[var(--c-800)] border-2 border-[var(--c-700)] flex items-center justify-center text-2xl font-bold text-[var(--c-100)]">
                    {mockUserInfo.avatar}
                  </div>
                  <div className="flex-1 pb-2">
                    <h3 className="text-lg font-bold text-[var(--c-100)]">{mockUserInfo.name}</h3>
                    <p className="text-sm text-[var(--c-500)]">{mockUserInfo.email}</p>
                  </div>
                  <button className="px-4 py-2 bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] rounded-lg text-sm font-medium transition-colors">
                    编辑资料
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-[var(--c-950)] border border-[var(--c-800)] rounded-xl p-4">
                    <div className="text-2xl font-bold text-[var(--c-100)]">{stats.running}</div>
                    <div className="text-xs text-[var(--c-500)] mt-1">运行中</div>
                  </div>
                  <div className="bg-[var(--c-950)] border border-[var(--c-800)] rounded-xl p-4">
                    <div className="text-2xl font-bold text-[var(--c-100)]">{stats.total}</div>
                    <div className="text-xs text-[var(--c-500)] mt-1">已安装</div>
                  </div>
                  <div className="bg-[var(--c-950)] border border-[var(--c-800)] rounded-xl p-4">
                    <div className="text-2xl font-bold text-[var(--c-100)]">{stats.builtin}</div>
                    <div className="text-xs text-[var(--c-500)] mt-1">内置插件</div>
                  </div>
                  <div className="bg-[var(--c-950)] border border-[var(--c-800)] rounded-xl p-4">
                    <div className="text-2xl font-bold text-[var(--c-100)]">{stats.user}</div>
                    <div className="text-xs text-[var(--c-500)] mt-1">用户插件</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 快捷操作 */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4 hover:border-[var(--c-700)] transition-colors cursor-pointer group">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                    <Puzzle size={20} className="text-blue-500" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">插件市场</div>
                    <div className="text-xs text-[var(--c-500)]">浏览和安装新插件</div>
                  </div>
                </div>
              </div>
              <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4 hover:border-[var(--c-700)] transition-colors cursor-pointer group">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                    <Download size={20} className="text-purple-500" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">下载管理</div>
                    <div className="text-xs text-[var(--c-500)]">管理下载任务</div>
                  </div>
                </div>
              </div>
              <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4 hover:border-[var(--c-700)] transition-colors cursor-pointer group">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                    <Bell size={20} className="text-amber-500" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">通知设置</div>
                    <div className="text-xs text-[var(--c-500)]">管理通知偏好</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 最近活动 */}
            <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-6">
              <h3 className="text-sm font-semibold text-[var(--c-200)] mb-4">最近活动</h3>
              <div className="space-y-3">
                <div className="flex items-center gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-[var(--c-400)]">Docker 管理器启动成功</span>
                  <span className="text-[var(--c-600)] ml-auto">2分钟前</span>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-blue-500" />
                  <span className="text-[var(--c-400)]">安装了软件安装器 v1.0.0</span>
                  <span className="text-[var(--c-600)] ml-auto">1小时前</span>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-[var(--c-500)]" />
                  <span className="text-[var(--c-400)]">更新了系统配置</span>
                  <span className="text-[var(--c-600)] ml-auto">昨天</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'plugins' && (
          <motion.div
            key="plugins"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            {/* 批量操作栏 */}
            {selectedPlugins.size > 0 && (
              <div className="bg-[var(--c-800)] border border-[var(--c-700)] rounded-xl p-3 flex items-center justify-between">
                <span className="text-sm text-[var(--c-300)]">已选择 {selectedPlugins.size} 个插件</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleBatchAction('start')}
                    className="px-3 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
                  >
                    批量启动
                  </button>
                  <button
                    onClick={() => handleBatchAction('stop')}
                    className="px-3 py-1.5 text-xs font-medium bg-[var(--c-700)] hover:bg-[var(--c-600)] text-[var(--c-200)] rounded-lg transition-colors"
                  >
                    批量停止
                  </button>
                  <button
                    onClick={() => handleBatchAction('uninstall')}
                    className="px-3 py-1.5 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                  >
                    批量卸载
                  </button>
                </div>
              </div>
            )}

            {/* 插件列表 */}
            <div className="space-y-3">
              {plugins.map((plugin) => {
                const statusConfig = getStatusConfig(plugin.status);
                const isSelected = selectedPlugins.has(plugin.id);
                const isBuiltin = plugin.path.startsWith('builtin/');

                return (
                  <div
                    key={plugin.id}
                    className={`bg-[var(--c-900)] border rounded-xl p-4 transition-all ${
                      isSelected ? 'border-blue-500 bg-blue-500/5' : 'border-[var(--c-800)] hover:border-[var(--c-700)]'
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {
                          const newSelected = new Set(selectedPlugins);
                          if (newSelected.has(plugin.id)) {
                            newSelected.delete(plugin.id);
                          } else {
                            newSelected.add(plugin.id);
                          }
                          setSelectedPlugins(newSelected);
                        }}
                        className="mt-1"
                      />
                      <div className="w-12 h-12 rounded-lg bg-[var(--c-800)] flex items-center justify-center flex-shrink-0">
                        <Puzzle size={24} className="text-[var(--c-500)]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="text-sm font-semibold text-[var(--c-100)]">{plugin.name}</h4>
                          {isBuiltin && (
                            <span className="px-1.5 py-0.5 bg-[var(--c-800)] text-[10px] text-[var(--c-500)] rounded">内置</span>
                          )}
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${statusConfig.bg} ${statusConfig.color} flex items-center gap-1`}>
                            <statusConfig.icon size={10} />
                            {statusConfig.label}
                          </span>
                        </div>
                        <p className="text-xs text-[var(--c-500)] mb-2 line-clamp-1">{plugin.description}</p>
                        <div className="flex items-center gap-4 text-[10px] text-[var(--c-600)]">
                          <span>v{plugin.version}</span>
                          <span>•</span>
                          <span>{plugin.author}</span>
                          <span>•</span>
                          <span>{plugin.size}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {plugin.status === 'running' && (
                          <button
                            onClick={() => handlePluginAction(plugin.id, 'stop')}
                            className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-red-400 transition-colors"
                            title="停止"
                          >
                            <Pause size={16} />
                          </button>
                        )}
                        {plugin.status === 'stopped' && (
                          <button
                            onClick={() => handlePluginAction(plugin.id, 'start')}
                            className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-emerald-400 transition-colors"
                            title="启动"
                          >
                            <Play size={16} />
                          </button>
                        )}
                        <button
                          onClick={() => handlePluginAction(plugin.id, 'restart')}
                          className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-blue-400 transition-colors"
                          title="重启"
                        >
                          <RotateCcw size={16} />
                        </button>
                        {!isBuiltin && (
                          <button
                            onClick={() => handlePluginAction(plugin.id, 'uninstall')}
                            className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-red-400 transition-colors"
                            title="卸载"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}

        {activeTab === 'settings' && (
          <motion.div
            key="settings"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl divide-y divide-[var(--c-800)]">
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Palette size={20} className="text-[var(--c-500)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">主题外观</div>
                    <div className="text-xs text-[var(--c-500)]">自定义界面主题和颜色</div>
                  </div>
                </div>
                <button className="text-xs text-[var(--c-400)] hover:text-[var(--c-200)]">配置</button>
              </div>

              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Globe size={20} className="text-[var(--c-500)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">语言和地区</div>
                    <div className="text-xs text-[var(--c-500)]">设置语言和时区偏好</div>
                  </div>
                </div>
                <div className="text-xs text-[var(--c-500)]">简体中文</div>
              </div>

              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Bell size={20} className="text-[var(--c-500)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">通知设置</div>
                    <div className="text-xs text-[var(--c-500)]">管理推送通知和提醒</div>
                  </div>
                </div>
                <button className="text-xs text-[var(--c-400)] hover:text-[var(--c-200)]">配置</button>
              </div>

              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <HardDrive size={20} className="text-[var(--c-500)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">存储管理</div>
                    <div className="text-xs text-[var(--c-500)]">清理缓存和临时文件</div>
                  </div>
                </div>
                <button className="text-xs text-[var(--c-400)] hover:text-[var(--c-200)]">清理</button>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'security' && (
          <motion.div
            key="security"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl divide-y divide-[var(--c-800)]">
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Mail size={20} className="text-[var(--c-500)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">邮箱</div>
                    <div className="text-xs text-[var(--c-500)]">{mockUserInfo.email}</div>
                  </div>
                </div>
                <button className="text-xs text-blue-400 hover:text-blue-300">修改</button>
              </div>

              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Shield size={20} className="text-[var(--c-500)]" />
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">密码</div>
                    <div className="text-xs text-[var(--c-500)]">•••••••••</div>
                  </div>
                </div>
                <button className="text-xs text-blue-400 hover:text-blue-300">修改</button>
              </div>

              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Power size={20} className="text-red-500" />
                  <div>
                    <div className="text-sm font-medium text-red-400">退出登录</div>
                    <div className="text-xs text-[var(--c-600)]">退出后需要重新登录</div>
                  </div>
                </div>
                <button className="text-xs text-red-400 hover:text-red-300">退出</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ProfileView;
