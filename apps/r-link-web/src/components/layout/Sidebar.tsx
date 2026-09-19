import { motion } from 'framer-motion';
import { Command, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { SidebarItem } from '../common';
import { routes, routesByGroupId, type RouteId } from '@/constants';

export interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  activeRoute: RouteId;
  onRouteChange: (route: RouteId) => void;
}
const groups = [ ['overview', '概览'], ['network', '网络管理'], ['storage', '数据存储'], ['extensions', '扩展应用'] ];

export function Sidebar({ collapsed, onToggle, activeRoute, onRouteChange }: SidebarProps) {
  return <motion.div animate={{ width: collapsed ? 80 : 256 }} className="bg-[var(--c-950)] border-r border-[var(--c-800)] flex flex-col flex-shrink-0 z-20 relative">
    <div className={`p-6 flex items-center ${collapsed ? 'justify-center flex-col gap-4' : 'justify-between'}`}>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[var(--c-100)] text-[var(--c-950)]"><Command size={18} /></div>
        {!collapsed && <h1 className="text-lg font-bold text-[var(--c-100)]">R-Link</h1>}
      </div>
      <button onClick={onToggle} aria-label={collapsed ? '展开侧栏' : '收起侧栏'} className="p-2 text-[var(--c-500)] hover:text-[var(--c-200)]">
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
      </button>
    </div>
    <nav className="flex-1 px-3 space-y-1 overflow-y-auto overflow-x-hidden">
      {groups.map(([id, label]) => <div key={id}>
        {!collapsed && <div className="px-3 mb-2 mt-6 text-[10px] font-semibold text-[var(--c-600)]">{label}</div>}
        {routesByGroupId[id].map(routeId => {
          const route = routes.find(item => item.id === routeId)!;
          return <SidebarItem key={route.id} icon={route.icon} label={route.label} active={activeRoute === route.id} onClick={() => onRouteChange(route.id)} collapsed={collapsed} badge={route.badge} />;
        })}
      </div>)}
    </nav>
    <div className="p-4 border-t border-[var(--c-800)] text-xs text-[var(--c-500)]">{collapsed ? '0.1' : 'R-Link Client · v0.1.0'}</div>
  </motion.div>;
}
export default Sidebar;
