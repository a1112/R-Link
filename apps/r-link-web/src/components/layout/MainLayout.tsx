/**
 * 主布局组件
 * 包含侧边栏和顶部导航栏
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { UserMenu, SettingsModal } from "../modals";
import { TermsModal } from "../modals/TermsModal";
import type { RouteId, ThemeName } from "@/constants";

export interface MainLayoutProps {
  /** 当前激活的路由 */
  activeRoute: RouteId;
  /** 路由变更回调 */
  onRouteChange: (route: RouteId) => void;
  /** 是否游客模式 */
  isGuest?: boolean;
  /** 当前主题 */
  currentTheme?: ThemeName;
  /** 主题变更回调 */
  onThemeChange?: (theme: ThemeName) => void;
  /** 登出回调 */
  onLogout?: () => void;
  /** 用户信息 */
  userInfo?: {
    name?: string;
    email?: string;
    avatar?: string;
  };
  /** 子内容 */
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  activeRoute,
  onRouteChange,
  isGuest = false,
  currentTheme = 'zinc',
  onThemeChange,
  onLogout,
  userInfo = {},
  children,
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showTerms, setShowTerms] = useState(false);

  const handleLogout = () => {
    setShowUserMenu(false);
    onLogout?.();
  };

  return (
    <div className="flex w-full h-full">
      {/* 侧边栏 */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        activeRoute={activeRoute}
        onRouteChange={onRouteChange}
        isGuest={isGuest}
      />

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[var(--c-950)] relative">
        {/* 顶部导航栏 */}
        <Header
          title={getRouteTitle(activeRoute)}
          username={userInfo.name}
          userEmail={userInfo.email}
          avatar={userInfo.avatar}
          isGuest={isGuest}
          onUserMenuClick={() => setShowUserMenu(!showUserMenu)}
        />

        {/* 内容区域 */}
        <div className="flex-1 overflow-hidden p-6 relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeRoute}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: 0.15 }}
              className="h-full"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* 用户菜单弹窗 */}
      <AnimatePresence>
        {showUserMenu && (
          <UserMenu
            show={showUserMenu}
            onClose={() => setShowUserMenu(false)}
            onOpenSettings={() => {
              setShowUserMenu(false);
              setShowSettings(true);
            }}
            onOpenTerms={() => {
              setShowTerms(true);
            }}
            onLogout={handleLogout}
            isGuest={isGuest}
            userInfo={userInfo}
          />
        )}
      </AnimatePresence>

      {/* 设置弹窗 */}
      <SettingsModal
        show={showSettings}
        onClose={() => setShowSettings(false)}
        currentTheme={currentTheme}
        onThemeChange={(theme) => {
          onThemeChange?.(theme);
        }}
      />

      {/* 用户协议弹窗 */}
      <TermsModal
        show={showTerms}
        onClose={() => setShowTerms(false)}
        onAgree={() => setShowTerms(false)}
        forceAgree={false}
      />
    </div>
  );
};

/**
 * 获取路由标题 */
function getRouteTitle(route: RouteId): string {
  const titles: Record<RouteId, string> = {
    dashboard: '仪表盘',
    analytics: '数据分析',
    network: '网络拓扑管理',
    remote: '设备列表',
    frp: '内网穿透',
    domains: '域名管理',
    storage: '文件管理',
    plugins: '插件中心',
    downloads: '下载管理',
    ssh: 'SSH 终端',
    console: 'Web 控制台',
    profile: '个人中心',
  };
  return titles[route] || 'R-Link';
}

export default MainLayout;
