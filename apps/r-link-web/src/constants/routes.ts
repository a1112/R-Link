/**
 * 路由和导航配置
 */

import {
  LayoutGrid,
  Activity,
  Share2,
  Network,
  Monitor,
  Globe,
  Link,
  Folder,
  Puzzle,
  User,
  Download,
  Terminal,
} from "lucide-react";

export type RouteId =
  | 'dashboard'
  | 'analytics'
  | 'network'
  | 'mesh'
  | 'remote'
  | 'frp'
  | 'domains'
  | 'storage'
  | 'plugins'
  | 'downloads'
  | 'ssh'
  | 'console';

export interface RouteConfig {
  id: RouteId;
  label: string;
  icon: import("lucide-react").LucideIcon;
  title: string;
  description?: string;
  badge?: number | string;
}

export const routes: RouteConfig[] = [
  {
    id: 'dashboard',
    label: '仪表盘',
    icon: LayoutGrid,
    title: '仪表盘',
    description: '系统概览与状态监控',
  },
  {
    id: 'analytics',
    label: '流量监控',
    icon: Activity,
    title: '服务端流量监控',
    description: '服务端网络接口实时流量',
  },
  {
    id: 'network',
    label: '设备连接视图',
    icon: Share2,
    title: '设备连接视图',
    description: '已登记设备及 TCP 检测结果',
  },
  {
    id: 'mesh',
    label: '虚拟组网',
    icon: Network,
    title: 'NetBird 虚拟组网',
    description: '真实节点、入网密钥、访问策略和网络路由',
  },
  {
    id: 'remote',
    label: '设备列表',
    icon: Monitor,
    title: '远程设备',
    description: '管理远程连接与终端节点',
  },
  {
    id: 'frp',
    label: '内网穿透',
    icon: Globe,
    title: '隧道列表',
    description: 'FRP 反向代理配置与管理',
  },
  {
    id: 'domains',
    label: '域名管理',
    icon: Link,
    title: '域名管理',
    description: '绑定自定义域名与 SSL 证书管理',
  },
  {
    id: 'storage',
    label: '共享文件',
    icon: Folder,
    title: '服务端共享文件',
    description: '共享区浏览、上传和下载',
  },
  {
    id: 'plugins',
    label: '插件中心',
    icon: Puzzle,
    title: '插件中心',
    description: '扩展 R-Link 的功能与特性',
  },
  {
    id: 'downloads',
    label: '下载管理',
    icon: Download,
    title: '下载管理',
    description: '服务端后台下载队列与续传',
  },
  {
    id: 'ssh',
    label: 'SSH 终端',
    icon: Terminal,
    title: 'SSH 终端',
    description: 'Web SSH 终端连接管理',
  },
  {
    id: 'console',
    label: 'Web 控制台',
    icon: Monitor,
    title: 'Web 控制台',
    description: '本地终端访问 (ttyd)',
  },

];

export const routesByGroupId: Record<string, RouteId[]> = {
  overview: ['dashboard', 'analytics'],
  network: ['network', 'mesh', 'remote', 'ssh', 'console', 'frp', 'domains'],
  storage: ['storage'],
  extensions: ['plugins', 'downloads'],
};

export const getRouteById = (id: RouteId): RouteConfig | undefined => {
  return routes.find(route => route.id === id);
};
