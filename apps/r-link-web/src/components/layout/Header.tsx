/**
 * 顶部导航栏组件
 */

import React from "react";
import { Search, Bell, User, Puzzle } from "lucide-react";

export interface HeaderProps {
  /** 当前页面标题 */
  title: string;
  /** 用户名 */
  username?: string;
  /** 用户邮箱 */
  userEmail?: string;
  /** 是否游客模式 */
  isGuest?: boolean;
  /** 用户头像/首字母 */
  avatar?: string;
  /** 搜索框占位符 */
  searchPlaceholder?: string;
  /** 用户菜单点击回调 */
  onUserMenuClick?: () => void;
  /** 搜索输入回调 */
  onSearch?: (query: string) => void;
  /** 通知点击回调 */
  onNotificationClick?: () => void;
  /** 是否有未读通知 */
  hasUnreadNotifications?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  isGuest = false,
  username,
  userEmail,
  avatar,
  searchPlaceholder = "搜索...",
  onUserMenuClick,
  onSearch,
  onNotificationClick,
  hasUnreadNotifications = true,
}) => {
  const defaultUsername = username || (isGuest ? 'Guest' : 'Admin User');
  const defaultUserEmail = userEmail || (isGuest ? 'guest@r-link.net' : 'admin@r-link.net');
  const defaultAvatar = isGuest ? '' : 'RL';
  const displayAvatar = avatar || defaultAvatar;

  return (
    <header className="h-12 border-b border-[var(--c-800)] bg-[var(--c-950)] flex items-center justify-between px-4 shrink-0 select-none" style={{ WebkitAppRegion: 'drag' }}>
      {/* 左侧：页面标题 */}
      <div className="flex items-center gap-2" style={{ WebkitAppRegion: 'no-drag' }}>
        <h2 className="text-sm font-semibold text-[var(--c-200)]">{title}</h2>
      </div>

      {/* 右侧：搜索与操作按钮 */}
      <div className="flex items-center gap-3" style={{ WebkitAppRegion: 'no-drag' }}>
        {/* 搜索框 */}
        <div className="flex items-center gap-2 text-[var(--c-400)] w-48 bg-[var(--c-900-50)] border border-[var(--c-800)] rounded-md px-2.5 py-1 transition-colors hover:border-[var(--c-700)] hover:bg-[var(--c-900)] focus-within:border-[var(--c-600)] focus-within:bg-[var(--c-900)]">
          <Search size={13} className="text-[var(--c-500)] shrink-0" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            className="bg-transparent border-none text-xs text-[var(--c-200)] w-full outline-none placeholder:text-[var(--c-600)] h-5"
            onChange={(e) => onSearch?.(e.target.value)}
          />
        </div>

        <div className="h-4 w-px bg-[var(--c-800)]" />

        {/* 通知按钮 */}
        <button
          onClick={onNotificationClick}
          className="relative p-2 text-[var(--c-500)] hover:text-[var(--c-200)] hover:bg-[var(--c-800-50)] rounded-lg transition-colors"
        >
          <Bell size={20} />
          {hasUnreadNotifications && (
            <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border-2 border-[var(--c-950)]"></span>
          )}
        </button>

        <div className="h-6 w-px bg-[var(--c-800)] mx-1" />

        {/* 用户按钮 */}
        <button
          onClick={onUserMenuClick}
          className="flex items-center gap-3 pl-2 pr-1 py-1 rounded-lg hover:bg-[var(--c-800-50)] transition-colors group"
        >
          <div className="text-right hidden sm:block">
            <div className="text-sm font-medium text-[var(--c-200)] group-hover:text-[var(--c-100)]">{defaultUsername}</div>
            <div className="text-xs text-[var(--c-500)]">{defaultUserEmail}</div>
          </div>
          <div className={`w-9 h-9 rounded-lg border flex items-center justify-center text-sm font-medium transition-colors ${
            isGuest
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-500'
              : 'bg-[var(--c-800)] border-[var(--c-700)] text-[var(--c-300)]'
          }`}>
            {displayAvatar || <User size={16} />}
          </div>
        </button>
      </div>
    </header>
  );
};

export default Header;
