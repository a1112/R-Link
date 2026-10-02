/**
 * 模拟数据常量
 */

import { Activity, Terminal, Server, Zap, Archive } from "lucide-react";

// ========== 流量数据 ==========
export const trafficData = Array.from({ length: 12 }, (_, i) => ({
  time: `${i * 2}:00`,
  upload: Math.floor(Math.random() * 30) + 10,
  download: Math.floor(Math.random() * 60) + 20,
}));

// ========== 设备数据 ==========
export const devices = [
  { id: 1, name: "工作站-Pro", os: "Windows 11 Pro", status: "online", ip: "10.0.0.4", type: "desktop", cpu: 12, ram: 45 },
  { id: 2, name: "MacBook-Air-M2", os: "macOS Sequoia", status: "online", ip: "10.0.0.7", type: "laptop", cpu: 8, ram: 60 },
  { id: 3, name: "Ubuntu-VPS-01", os: "Ubuntu 22.04 LTS", status: "online", ip: "192.168.1.5", type: "server", cpu: 5, ram: 20 },
  { id: 4, name: "NAS-存储服务", os: "TrueNAS Scale", status: "offline", ip: "10.0.0.100", type: "server", cpu: 0, ram: 0 },
];

// ========== 隧道数据 ==========
export const tunnels = [
  { id: 1, name: "博客预览", type: "HTTP", local: ":3000", remote: "blog.r-link.net", status: "active", latency: "12ms" },
  { id: 2, name: "SSH网关", type: "TCP", local: ":22", remote: "ssh.r-link.net:22022", status: "active", latency: "45ms" },
  { id: 3, name: "游戏服务器", type: "UDP", local: ":25565", remote: "play.r-link.net", status: "stopped", latency: "-" },
];

// ========== 域名数据 ==========
export const domains = [
  { id: 1, name: "blog.r-link.net", target: "127.0.0.1:3000", ssl: "Active", status: "active", expiry: "2024-12-31" },
  { id: 2, name: "api.r-link.net", target: "192.168.1.5:8080", ssl: "Active", status: "active", expiry: "2024-11-15" },
  { id: 3, name: "dev.r-link.net", target: "10.0.0.7:5000", ssl: "Expired", status: "warning", expiry: "2023-10-01" },
];

// ========== 拓扑数据 ==========
export const initialNodes = [
  { id: 'cloud', type: 'cloud', x: 400, y: 100, label: '互联网 / 云端', status: 'active' },
  { id: 'router', type: 'router', x: 400, y: 250, label: '核心网关', status: 'active' },
  { id: 'switch', type: 'switch', x: 400, y: 400, label: '交换机', status: 'active' },
  { id: 'pc1', type: 'desktop', x: 200, y: 550, label: '工作站 01', status: 'active' },
  { id: 'pc2', type: 'laptop', x: 350, y: 550, label: '移动办公 Mac', status: 'active' },
  { id: 'server1', type: 'server', x: 500, y: 550, label: '应用服务器', status: 'active' },
  { id: 'nas', type: 'server', x: 650, y: 550, label: 'NAS 存储', status: 'warning' },
];

export const initialLinks = [
  { source: 'cloud', target: 'router', type: 'wan' },
  { source: 'router', target: 'switch', type: 'lan' },
  { source: 'switch', target: 'pc1', type: 'lan' },
  { source: 'switch', target: 'pc2', type: 'lan' },
  { source: 'switch', target: 'server1', type: 'lan' },
  { source: 'switch', target: 'nas', type: 'lan' },
];

// ========== 文件数据 ==========
export const files = [
  { id: 1, name: "网站备份_2023.zip", size: "2.4 GB", date: "10月 24", type: "archive" },
  { id: 2, name: "设计规范系统", size: "-", date: "10月 23", type: "folder" },
  { id: 3, name: "季度财务报告.pdf", size: "4.2 MB", date: "10月 22", type: "document" },
  { id: 4, name: "nginx.conf", size: "2 KB", date: "10月 21", type: "code" },
];

// ========== 模拟插件数据 ==========
export const marketPlugins = [
  {
    id: "p1",
    name: "高级流量分析",
    description: "提供更详细的流量监控图表，支持应用层协议识别与统计。",
    author: "R-Link Team",
    version: "2.1.0",
    downloads: "12k",
    rating: 4.8,
    status: "installed",
    verified: true,
    icon: Activity,
    features: ["应用层协议识别", "历史流量回溯", "自定义报表导出", "异常流量告警"]
  },
  {
    id: "p2",
    name: "Web终端增强",
    description: "为内置SSH终端添加主题支持、多窗口分屏与Zmodem文件传输功能。",
    author: "Community",
    version: "1.0.5",
    downloads: "8.5k",
    rating: 4.5,
    status: "update_available",
    verified: false,
    icon: Terminal,
    features: ["Zmodem文件传输", "多窗口分屏", "Solarized主题", "快捷命令片段"]
  },
  {
    id: "p3",
    name: "Docker容器管理",
    description: "直接在设备列表中管理远程主机的Docker容器，支持启动、停止与日志查看。",
    author: "Docker Inc.",
    version: "3.2.1",
    downloads: "45k",
    rating: 4.9,
    status: "not_installed",
    verified: true,
    icon: Server,
    features: ["容器生命周期管理", "实时日志流", "镜像管理", "Compose支持"]
  },
  {
    id: "p4",
    name: "网络测速工具",
    description: "集成iperf3与Speedtest，一键测试节点间的带宽与延迟。",
    author: "NetworkTools",
    version: "0.9.8",
    downloads: "3k",
    rating: 4.2,
    status: "not_installed",
    verified: false,
    icon: Zap,
    features: ["iperf3集成", "Speedtest节点测速", "历史记录对比", "图形化报告"]
  },
  {
    id: "p5",
    name: "自动备份助手",
    description: "定期自动备份关键配置文件到云端存储，防止数据丢失。",
    author: "R-Link Team",
    version: "1.5.0",
    downloads: "15k",
    rating: 4.7,
    status: "installed",
    verified: true,
    icon: Archive,
    features: ["定时自动备份", "多版本保留", "加密存储", "一键恢复"]
  },
];
