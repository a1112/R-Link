/**
 * 统计卡片组件
 * 用于仪表盘等页面显示统计数据
 */

import React from "react";
import type { LucideIcon } from "lucide-react";

export interface StatCardProps {
  /** 标题 */
  title: string;
  /** 显示的数值 */
  value: string | number;
  /** 副标题/趋势描述 */
  sub?: string;
  /** 图标组件 */
  icon: LucideIcon;
  /** 趋势方向 */
  trend?: 'up' | 'down' | 'neutral';
  /** 是否加载中 */
  loading?: boolean;
  /** 额外的类名 */
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  sub,
  icon: Icon,
  trend,
  loading = false,
  className = '',
}) => {
  const trendColors = {
    up: "bg-emerald-500/10 text-emerald-500",
    down: "bg-red-500/10 text-red-500",
    neutral: "bg-[var(--c-800)] text-[var(--c-500)]",
  };

  return (
    <div className={`bg-[var(--c-900)] border border-[var(--c-800)] p-6 rounded-xl flex flex-col justify-between h-full hover:border-[var(--c-700)] transition-colors duration-300 ${className}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="p-2 bg-[var(--c-800)] rounded-lg text-[var(--c-400)]">
          <Icon size={20} />
        </div>
        {sub && trend && (
          <span className={`text-xs font-medium px-2 py-1 rounded-full ${trendColors[trend]}`}>
            {sub}
          </span>
        )}
        {loading && (
          <div className="animate-pulse text-xs text-[var(--c-500)]">加载中...</div>
        )}
      </div>
      <div>
        <div className="text-2xl font-bold text-[var(--c-100)] tracking-tight">
          {loading ? '--' : value}
        </div>
        <div className="text-sm text-[var(--c-500)] mt-1 font-medium">{title}</div>
      </div>
    </div>
  );
};

export default StatCard;
