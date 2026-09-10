/**
 * 状态徽章组件
 * 用于显示各种状态（在线、离线、运行中等）
 */

import React from "react";

export type StatusType = 'active' | 'online' | 'running' | 'stopped' | 'offline' | 'warning' | 'error' | 'unknown';

export interface StatusBadgeProps {
  /** 状态类型 */
  status: StatusType;
  /** 自定义标签文本 */
  label?: string;
  /** 额外的类名 */
  className?: string;
  /** 大小变体 */
  size?: 'sm' | 'md' | 'lg';
}

const statusConfig: Record<StatusType, { label: string; className: string }> = {
  active: { label: '运行中', className: 'bg-emerald-500/5 border-emerald-500/20 text-emerald-500' },
  online: { label: '在线', className: 'bg-emerald-500/5 border-emerald-500/20 text-emerald-500' },
  running: { label: '运行中', className: 'bg-emerald-500/5 border-emerald-500/20 text-emerald-500' },
  stopped: { label: '已停止', className: 'bg-[var(--c-500-5)] border-[var(--c-500-20)] text-[var(--c-500)]' },
  offline: { label: '离线', className: 'bg-[var(--c-500-5)] border-[var(--c-500-20)] text-[var(--c-500)]' },
  warning: { label: '告警', className: 'bg-amber-500/10 border-amber-500/20 text-amber-500' },
  error: { label: '错误', className: 'bg-red-500/10 border-red-500/20 text-red-500' },
  unknown: { label: '未知', className: 'bg-[var(--c-500-5)] border-[var(--c-500-20)] text-[var(--c-500)]' },
};

const sizeClasses = {
  sm: 'px-2 py-0.5 text-[10px]',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  className = '',
  size = 'md',
}) => {
  const config = statusConfig[status] || statusConfig.unknown;
  const displayLabel = label || config.label;

  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-md border font-medium ${config.className} ${sizeClasses[size]} ${className}`}
    >
      <div className={`w-1.5 h-1.5 rounded-full ${
        status === 'active' || status === 'online' || status === 'running'
          ? 'bg-emerald-500'
          : status === 'warning'
          ? 'bg-amber-500'
          : status === 'error'
          ? 'bg-red-500'
          : 'bg-[var(--c-500)]'
      }`} />
      {displayLabel}
    </div>
  );
};

export default StatusBadge;
