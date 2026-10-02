/**
 * 内网穿透（隧道管理）页面组件
 */

import React from "react";
import { Plus, Globe, MoreHorizontal } from "lucide-react";
import { tunnels } from "@/constants/mockData";
import { StatusBadge } from "../common";

export const FRPView: React.FC = () => {
  const getTypeBadgeColor = (type: string) => {
    const colors = {
      HTTP: 'bg-blue-500/10 text-blue-500',
      TCP: 'bg-emerald-500/10 text-emerald-500',
      UDP: 'bg-amber-500/10 text-amber-500',
    };
    return colors[type as keyof typeof colors] || 'bg-[var(--c-800)] text-[var(--c-400)]';
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">隧道列表</h2>
          <p className="text-[var(--c-500)] text-sm">FRP 反向代理配置与管理</p>
        </div>
        <button className="bg-[var(--c-100)] hover:bg-[var(--c-white)] text-[var(--c-900)] px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
          <Plus size={16} /> 新建隧道
        </button>
      </div>

      <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--c-800)] text-[var(--c-500)]">
              <th className="p-4 font-medium w-12">#</th>
              <th className="p-4 font-medium">名称</th>
              <th className="p-4 font-medium">类型</th>
              <th className="p-4 font-medium">本地端点</th>
              <th className="p-4 font-medium">远程地址</th>
              <th className="p-4 font-medium">状态</th>
              <th className="p-4 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--c-800-50)]">
            {tunnels.map((tunnel) => (
              <tr key={tunnel.id} className="group hover:bg-[var(--c-800-30)] transition-colors">
                <td className="p-4 text-[var(--c-600)] font-mono">{tunnel.id}</td>
                <td className="p-4 font-medium text-[var(--c-200)]">{tunnel.name}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded bg-[var(--c-800)] text-[var(--c-400)] text-xs font-mono ${getTypeBadgeColor(tunnel.type)}`}>
                    {tunnel.type}
                  </span>
                </td>
                <td className="p-4 text-[var(--c-400)] font-mono text-xs">{tunnel.local}</td>
                <td className="p-4 text-[var(--c-400)] font-mono text-xs text-blue-400 hover:underline cursor-pointer">{tunnel.remote}</td>
                <td className="p-4">
                  <StatusBadge status={tunnel.status === 'active' ? 'active' : 'stopped'} />
                </td>
                <td className="p-4 text-right">
                  <button className="p-2 text-[var(--c-500)] hover:text-[var(--c-200)] hover:bg-[var(--c-800)] rounded-md transition-colors">
                    <MoreHorizontal size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default FRPView;
