/**
 * 仪表盘视图组件
 * 使用后端API获取系统资源数据
 */

import React, { useMemo } from "react";
import { Activity, Server, Monitor, Globe, HardDrive, CheckCircle2, AlertCircle, Puzzle } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useSystemResources, usePlugins } from "@/api/hooks";

const StatCard = ({ title, value, sub, icon: Icon, trend }: {
  title: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
}) => (
  <div className="bg-[var(--c-900)] border border-[var(--c-800)] p-6 rounded-xl flex flex-col justify-between h-full hover:border-[var(--c-700)] transition-colors duration-300">
    <div className="flex items-start justify-between mb-4">
      <div className="p-2 bg-[var(--c-800)] rounded-lg text-[var(--c-400)]">
        <Icon size={20} />
      </div>
      {sub && trend && (
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${
          trend === 'up'
            ? "bg-emerald-500/10 text-emerald-500"
            : trend === 'down'
            ? "bg-red-500/10 text-red-500"
            : "bg-[var(--c-800)] text-[var(--c-500)]"
        }`}>
          {sub}
        </span>
      )}
    </div>
    <div>
      <div className="text-2xl font-bold text-[var(--c-100)] tracking-tight">{value}</div>
      <div className="text-sm text-[var(--c-500)] mt-1 font-medium">{title}</div>
    </div>
  </div>
);

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};

const formatPercent = (value: number): string => {
  return `${Math.round(value)}%`;
};

export const DashboardView: React.FC = () => {
  // 获取系统资源数据
  const { data: resources, loading: resourcesLoading, error: resourcesError } = useSystemResources(5000);

  // 获取插件数据
  const { data: plugins, loading: pluginsLoading, refetch: refetchPlugins } = usePlugins();

  // 生成流量模拟数据（实际应从API获取）
  const trafficData = useMemo(() => {
    return Array.from({ length: 12 }, (_, i) => ({
      time: `${i * 2}:00`,
      upload: Math.floor(Math.random() * 30) + 10,
      download: Math.floor(Math.random() * 60) + 20,
    }));
  }, []);

  // 计算统计数据
  const stats = useMemo(() => {
    if (!resources) {
      return {
        cpuPercent: 0,
        memoryPercent: 0,
        diskUsed: '0 GB',
        diskPercent: 0,
        onlinePlugins: 0,
        totalPlugins: 0,
      };
    }

    const onlinePlugins = plugins?.filter(p =>
      p.status?.status === 'running'
    ).length ?? 0;

    return {
      cpuPercent: resources.cpu.percent,
      memoryPercent: resources.memory.percent,
      diskUsed: formatBytes(resources.disk.used),
      diskPercent: resources.disk.percent,
      onlinePlugins,
      totalPlugins: plugins?.length ?? 0,
    };
  }, [resources, plugins]);

  // 系统健康状态
  const systemHealth = useMemo(() => {
    if (!resources) return { status: 'unknown', message: '正在加载...' };

    const { cpuPercent, memoryPercent, diskPercent } = stats;

    if (cpuPercent > 90 || memoryPercent > 90 || diskPercent > 95) {
      return { status: 'critical', message: '系统资源紧张' };
    }
    if (cpuPercent > 70 || memoryPercent > 80 || diskPercent > 85) {
      return { status: 'warning', message: '资源使用较高' };
    }
    return { status: 'healthy', message: '所有系统运行正常' };
  }, [stats, resources]);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="活跃插件"
          value={`${stats.onlinePlugins}/${stats.totalPlugins}`}
          sub={pluginsLoading ? '加载中...' : '运行中'}
          icon={Puzzle}
        />
        <StatCard
          title="网络流量"
          value="1.2 GB"
          sub="+12% 较上周"
          icon={Activity}
          trend="up"
        />
        <StatCard
          title="活跃隧道"
          value="2"
          sub="运行稳定"
          icon={Globe}
        />
        <StatCard
          title="存储已用"
          value={stats.diskUsed}
          sub={`${formatPercent(stats.diskPercent)} 已用`}
          icon={HardDrive}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 图表区域 */}
        <div className="lg:col-span-2 bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-6">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-[var(--c-100)] font-semibold text-lg">网络活动监控</h3>
              <p className="text-[var(--c-500)] text-sm mt-1">入站与出站流量实时概览</p>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1.5 text-xs font-medium text-[var(--c-400)] hover:text-[var(--c-100)] bg-[var(--c-800-50)] hover:bg-[var(--c-800)] rounded-md transition-colors">24小时</button>
              <button className="px-3 py-1.5 text-xs font-medium text-[var(--c-100)] bg-[var(--c-800)] rounded-md">7天</button>
              <button className="px-3 py-1.5 text-xs font-medium text-[var(--c-400)] hover:text-[var(--c-100)] bg-[var(--c-800-50)] hover:bg-[var(--c-800)] rounded-md transition-colors">30天</button>
            </div>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trafficData}>
                <defs>
                  <linearGradient id="colorDown" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorUp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.1} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--c-800)" vertical={false} />
                <XAxis dataKey="time" stroke="var(--c-600)" fontSize={12} tickLine={false} axisLine={false} dy={10} />
                <YAxis stroke="var(--c-600)" fontSize={12} tickLine={false} axisLine={false} dx={-10} />
                <Tooltip
                  contentStyle={{ backgroundColor: "var(--c-900)", borderColor: "var(--c-800)", color: "var(--c-100)", borderRadius: "8px", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)" }}
                  itemStyle={{ color: "var(--c-200)" }}
                  cursor={{ stroke: "var(--c-700)", strokeWidth: 1 }}
                />
                <Area type="monotone" dataKey="download" stroke="#3b82f6" strokeWidth={2} fill="url(#colorDown)" name="下载 (Mbps)" />
                <Area type="monotone" dataKey="upload" stroke="#10b981" strokeWidth={2} fill="url(#colorUp)" name="上传 (Mbps)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 系统状态 */}
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-6 flex flex-col h-full">
          <h3 className="text-[var(--c-100)] font-semibold text-lg mb-1">系统健康状态</h3>
          <p className="text-[var(--c-500)] text-sm mb-6">核心组件实时性能指标</p>

          {resourcesError ? (
            <div className="flex-1 flex items-center justify-center text-[var(--c-500)]">
              <div className="text-center">
                <AlertCircle size={32} className="mx-auto mb-2 text-red-500" />
                <p className="text-sm">无法连接到后端服务</p>
                <p className="text-xs mt-1">请确保 R-Link Server 正在运行</p>
              </div>
            </div>
          ) : resourcesLoading ? (
            <div className="flex-1 flex items-center justify-center text-[var(--c-500)]">
              <div className="animate-pulse">加载中...</div>
            </div>
          ) : (
            <div className="space-y-6 flex-1">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--c-400)] font-medium">CPU 使用率</span>
                  <span className="text-[var(--c-200)]">{formatPercent(stats.cpuPercent)}</span>
                </div>
                <div className="h-2 w-full bg-[var(--c-800)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      stats.cpuPercent > 80 ? 'bg-red-500' : stats.cpuPercent > 60 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.min(stats.cpuPercent, 100)}%` }}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--c-400)] font-medium">内存 使用率</span>
                  <span className="text-[var(--c-200)]">{formatPercent(stats.memoryPercent)}</span>
                </div>
                <div className="h-2 w-full bg-[var(--c-800)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      stats.memoryPercent > 80 ? 'bg-red-500' : stats.memoryPercent > 60 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.min(stats.memoryPercent, 100)}%` }}
                  />
                </div>
                <div className="text-xs text-[var(--c-600)]">
                  {resources ? `${formatBytes(resources.memory.used)} / ${formatBytes(resources.memory.total)}` : '--'}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--c-400)] font-medium">存储空间</span>
                  <span className="text-[var(--c-200)]">{formatPercent(stats.diskPercent)}</span>
                </div>
                <div className="h-2 w-full bg-[var(--c-800)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      stats.diskPercent > 90 ? 'bg-red-500' : stats.diskPercent > 75 ? 'bg-amber-500' : 'bg-[var(--c-200)]'
                    }`}
                    style={{ width: `${Math.min(stats.diskPercent, 100)}%` }}
                  />
                </div>
                <div className="text-xs text-[var(--c-600)]">
                  {resources ? `${formatBytes(resources.disk.used)} / ${formatBytes(resources.disk.total)}` : '--'}
                </div>
              </div>

              <div className="pt-6 mt-auto border-t border-[var(--c-800)]">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${
                    systemHealth.status === 'healthy' ? 'bg-emerald-500/10 text-emerald-500' :
                    systemHealth.status === 'warning' ? 'bg-amber-500/10 text-amber-500' :
                    'bg-red-500/10 text-red-500'
                  }`}>
                    {systemHealth.status === 'healthy' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-[var(--c-200)]">{systemHealth.message}</div>
                    <div className="text-xs text-[var(--c-500)]">
                      {resourcesLoading ? '正在检查...' : '上次检查: 刚刚'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardView;
