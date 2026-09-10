/**
 * 侧边栏菜单项组件
 */

import React from "react";
import type { LucideIcon } from "lucide-react";

export interface SidebarItemProps {
  /** 图标组件 */
  icon: LucideIcon;
  /** 显示标签 */
  label: string;
  /** 是否激活 */
  active: boolean;
  /** 点击回调 */
  onClick: () => void;
  /** 是否折叠（仅显示图标） */
  collapsed: boolean;
  /** 是否禁用 */
  disabled?: boolean;
  /** 徽章/计数器 */
  badge?: number | string;
  /** 额外的类名 */
  className?: string;
}

export const SidebarItem: React.FC<SidebarItemProps> = ({
  icon: Icon,
  label,
  active,
  onClick,
  collapsed,
  disabled = false,
  badge,
  className = '',
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full flex items-center ${collapsed ? 'justify-center px-2' : 'gap-3 px-3'} py-2 rounded-lg transition-all duration-200 text-sm font-medium ${
        disabled
          ? 'opacity-50 cursor-not-allowed'
          : active
          ? "bg-[var(--c-800)] text-[var(--c-100)]"
          : "text-[var(--c-500)] hover:bg-[var(--c-800-50)] hover:text-[var(--c-300)]"
      } ${className}`}
      title={collapsed ? label : undefined}
    >
      <Icon size={18} strokeWidth={2} className="flex-shrink-0" />
      {!collapsed && (
        <>
          <span className="whitespace-nowrap overflow-hidden flex-1 text-left">{label}</span>
          {badge && (
            <span className="text-xs bg-[var(--c-700)] text-[var(--c-300)] px-1.5 py-0.5 rounded">
              {badge}
            </span>
          )}
        </>
      )}
    </button>
  );
};

export default SidebarItem;
