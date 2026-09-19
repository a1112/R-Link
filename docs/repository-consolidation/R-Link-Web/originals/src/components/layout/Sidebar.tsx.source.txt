/**
 * 侧边栏组件
 */

import React from "react";
import { motion } from "framer-motion";
import { Command, User, Shield, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { SidebarItem } from "../common";
import { routes, routesByGroupId } from "@/constants";
import type { RouteId } from "@/constants";

export interface SidebarProps {
  /** 是否折叠 */
  collapsed: boolean;
  /** 折叠切换回调 */
  onToggle: () => void;
  /** 当前激活的路由 */
  activeRoute: RouteId;
  /** 路由变更回调 */
  onRouteChange: (route: RouteId) => void;
  /** 是否游客模式 */
  isGuest?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  onToggle,
  activeRoute,
  onRouteChange,
  isGuest = false,
}) => {
  return (
    <motion.div
      animate={{ width: collapsed ? 80 : 256 }}
      className="bg-[var(--c-950)] border-r border-[var(--c-800)] flex flex-col flex-shrink-0 z-20 relative"
    >
      {/* 游客模式指示条 */}
      {isGuest && <div className="absolute top-0 left-0 w-1 bg-amber-500 h-full z-30" />}

      {/* Logo 区域 */}
      <div className={`p-6 flex items-center ${collapsed ? 'justify-center flex-col gap-4' : 'justify-between'}`}>
        <div className={`flex items-center gap-3 ${collapsed ? '' : 'flex-1 overflow-hidden'}`}>
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${isGuest ? 'bg-amber-500 text-black' : 'bg-[var(--c-100)] text-[var(--c-950)]'}`}>
            {isGuest ? <User size={18} strokeWidth={3} /> : <Command size={18} strokeWidth={3} />}
          </div>
          {!collapsed && (
            <h1 className="text-lg font-bold text-[var(--c-100)] tracking-tight whitespace-nowrap">
              {isGuest ? 'Guest Mode' : 'R-Link'}
            </h1>
          )}
        </div>
        <button
          onClick={onToggle}
          className="h-8 w-8 flex items-center justify-center rounded-lg border border-transparent hover:border-[var(--c-800)] hover:bg-[var(--c-900)] text-[var(--c-500)] hover:text-[var(--c-200)] transition-all duration-200 active:scale-95 shadow-sm hover:shadow"
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      {/* 导航菜单 */}
      <nav className="flex-1 px-3 space-y-1 overflow-y-auto overflow-x-hidden">
        {/* 概览分组 */}
        {!collapsed && <div className="px-3 mb-2 mt-2 text-[10px] font-semibold text-[var(--c-600)] uppercase tracking-wider whitespace-nowrap">概览</div>}
        {routesByGroupId.overview.map((routeId) => {
          const route = routes.find(r => r.id === routeId);
          if (!route) return null;
          return (
            <SidebarItem
              key={route.id}
              icon={route.icon}
              label={route.label}
              active={activeRoute === route.id}
              onClick={() => onRouteChange(route.id)}
              collapsed={collapsed}
              disabled={route.requireAuth && isGuest}
            />
          );
        })}

        {/* 网络管理分组 */}
        {!isGuest && (
          <>
            {!collapsed && <div className="px-3 mb-2 mt-6 text-[10px] font-semibold text-[var(--c-600)] uppercase tracking-wider whitespace-nowrap">网络管理</div>}
            {routesByGroupId.network.map((routeId) => {
              const route = routes.find(r => r.id === routeId);
              if (!route) return null;
              return (
                <SidebarItem
                  key={route.id}
                  icon={route.icon}
                  label={route.label}
                  active={activeRoute === route.id}
                  onClick={() => onRouteChange(route.id)}
                  collapsed={collapsed}
                />
              );
            })}
          </>
        )}

        {/* 数据存储分组 */}
        {!isGuest && (
          <>
            {!collapsed && <div className="px-3 mb-2 mt-6 text-[10px] font-semibold text-[var(--c-600)] uppercase tracking-wider whitespace-nowrap">数据存储</div>}
            {routesByGroupId.storage.map((routeId) => {
              const route = routes.find(r => r.id === routeId);
              if (!route) return null;
              return (
                <SidebarItem
                  key={route.id}
                  icon={route.icon}
                  label={route.label}
                  active={activeRoute === route.id}
                  onClick={() => onRouteChange(route.id)}
                  collapsed={collapsed}
                />
              );
            })}
          </>
        )}

        {/* 扩展应用分组 */}
        {!isGuest && (
          <>
            {!collapsed && <div className="px-3 mb-2 mt-6 text-[10px] font-semibold text-[var(--c-600)] uppercase tracking-wider whitespace-nowrap">扩展应用</div>}
            {routesByGroupId.extensions.map((routeId) => {
              const route = routes.find(r => r.id === routeId);
              if (!route) return null;
              return (
                <SidebarItem
                  key={route.id}
                  icon={route.icon}
                  label={route.label}
                  active={activeRoute === route.id}
                  onClick={() => onRouteChange(route.id)}
                  collapsed={collapsed}
                  badge={route.id === 'downloads' && undefined} // 可以下载数量
                />
              );
            })}
          </>
        )}

        {/* 个人中心分组 */}
        {!collapsed && <div className="px-3 mb-2 mt-6 text-[10px] font-semibold text-[var(--c-600)] uppercase tracking-wider whitespace-nowrap">个人</div>}
        {routesByGroupId.personal.map((routeId) => {
          const route = routes.find(r => r.id === routeId);
          if (!route) return null;
          return (
            <SidebarItem
              key={route.id}
              icon={route.icon}
              label={route.label}
              active={activeRoute === route.id}
              onClick={() => onRouteChange(route.id)}
              collapsed={collapsed}
            />
          );
        })}

        {/* 游客模式提示 */}
        {isGuest && (
          <div className="mt-4 px-3 py-4 bg-[var(--c-900)] rounded-xl border border-[var(--c-800)] text-center">
            <div className="mb-2 flex justify-center text-amber-500"><Shield size={24} /></div>
            {!collapsed && (
              <>
                <h4 className="text-xs font-bold text-[var(--c-200)] mb-1">受限访问</h4>
                <p className="text-[10px] text-[var(--c-500)] leading-tight">游客模式下部分功能不可用，请登录以解锁全部功能。</p>
              </>
            )}
          </div>
        )}
      </nav>

      {/* 底部版本信息 */}
      <div className="p-4 border-t border-[var(--c-800)] mt-auto overflow-hidden">
        <div className={`px-2 flex flex-col gap-2 ${collapsed ? 'items-center' : ''}`}>
          <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between'} w-full`}>
            {!collapsed && <span className="text-xs font-semibold text-[var(--c-400)] whitespace-nowrap">R-Link Client</span>}
            {!collapsed && <span className="text-[10px] font-mono text-[var(--c-600)]">v1.2.0</span>}
            {collapsed && <span className="text-[10px] font-mono text-[var(--c-600)]">v1.2</span>}
          </div>
          {!collapsed && (
            <div className="text-[10px] text-[var(--c-600)] leading-relaxed whitespace-nowrap">
              © 2026 R-Link Network.<br/>
              All rights reserved.
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default Sidebar;
