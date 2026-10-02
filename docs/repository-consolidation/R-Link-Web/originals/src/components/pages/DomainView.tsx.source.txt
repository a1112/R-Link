/**
 * 域名管理页面组件
 */

import React from "react";
import { Plus, Globe, MoreHorizontal } from "lucide-react";
import { domains } from "@/constants/mockData";
import { StatusBadge } from "../common";

export const DomainView: React.FC = () => {
  const getSslBadgeColor = (ssl: string) => {
    return ssl === 'Active'
      ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
      : 'bg-red-500/10 text-red-500 border-red-500/20';
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">域名管理</h2>
          <p className="text-[var(--c-500)] text-sm">绑定自定义域名与 SSL 证书管理</p>
        </div>
        <button className="bg-[var(--c-100)] hover:bg-[var(--c-white)] text-[var(--c-900)] px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
          <Plus size={16} /> 添加域名
        </button>
      </div>

      <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--c-800)] text-[var(--c-500)]">
              <th className="p-4 font-medium w-12">#</th>
              <th className="p-4 font-medium">域名</th>
              <th className="p-4 font-medium">指向目标</th>
              <th className="p-4 font-medium">SSL 证书</th>
              <th className="p-4 font-medium">过期时间</th>
              <th className="p-4 font-medium">状态</th>
              <th className="p-4 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--c-800-50)]">
            {domains.map((domain) => (
              <tr key={domain.id} className="group hover:bg-[var(--c-800-30)] transition-colors">
                <td className="p-4 text-[var(--c-600)] font-mono">{domain.id}</td>
                <td className="p-4 font-medium text-[var(--c-200)] flex items-center gap-2">
                  <Globe size={14} className="text-[var(--c-500)]" />
                  {domain.name}
                </td>
                <td className="p-4 text-[var(--c-400)] font-mono text-xs">{domain.target}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${getSslBadgeColor(domain.ssl)}`}>
                    {domain.ssl}
                  </span>
                </td>
                <td className="p-4 text-[var(--c-500)] text-xs">{domain.expiry}</td>
                <td className="p-4">
                  <StatusBadge status={domain.status === 'active' ? 'active' : 'warning'} />
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

export default DomainView;
