/**
 * 路由和导航配置
 */

import {
  LayoutGrid,
  Activity,
  Share2,
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
  | 'remote'
  | 'frp'
  | 'domains'
  | 'storage'
  | 'plugins'
  | 'profile'
  | 'downloads'
  | 'ssh'
  | 'console';

export interface RouteConfig {
  id: RouteId;
  label: string;
  icon: React.ElementType;
  title: string;
  description?: string;
  requireAuth?: boolean; // 是否需要登录
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
    label: '数据分析',
    icon: Activity,
    title: '数据分析',
    description: '流量分析与统计报表',
    requireAuth: true,
  },
  {
    id: 'network',
    label: '网络拓扑图',
    icon: Share2,
    title: '网络拓扑管理',
    description: '可视化管理虚拟局域网与设备连接',
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
    label: '文件管理',
    icon: Folder,
    title: '文件管理',
    description: 'WebDAV 云存储文件浏览器',
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
    description: '管理插件下载和更新任务',
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
  {
    id: 'profile',
    label: '我的',
    icon: User,
    title: '个人中心',
    description: '账户设置与个人偏好',
  },
];

export const routesByGroupId: Record<string, RouteId[]> = {
  overview: ['dashboard', 'analytics'],
  network: ['network', 'remote', 'ssh', 'console', 'frp', 'domains'],
  storage: ['storage'],
  extensions: ['plugins', 'downloads'],
  personal: ['profile'],
};

export const getRouteById = (id: RouteId): RouteConfig | undefined => {
  return routes.find(route => route.id === id);
};
