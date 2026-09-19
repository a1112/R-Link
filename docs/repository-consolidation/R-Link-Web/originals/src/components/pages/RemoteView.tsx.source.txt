/**
 * 远程设备管理页面组件
 */

import React from "react";
import { Plus, Monitor, Server, Terminal } from "lucide-react";
import { toast } from "sonner";
import { devices } from "@/constants/mockData";
import { StatusBadge } from "../common";

export const RemoteView: React.FC = () => {
  const handleConnect = (name: string, type: string) => {
    toast(`正在连接到 ${name}...`, {
      description: `正在建立安全 ${type} 会话连接`,
    });
  };

  const getDeviceIcon = (type: string) => {
    return type === 'desktop' || type === 'laptop' ? Monitor : Server;
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">远程设备</h2>
          <p className="text-[var(--c-500)] text-sm">管理远程连接与终端节点</p>
        </div>
        <button className="bg-[var(--c-100)] hover:bg-[var(--c-white)] text-[var(--c-900)] px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
          <Plus size={16} /> 添加设备
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {devices.map((device) => {
          const Icon = getDeviceIcon(device.type);
          return (
            <div key={device.id} className="group bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-5 hover:border-[var(--c-700)] transition-all duration-200">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-[var(--c-800)] rounded-lg flex items-center justify-center text-[var(--c-400)]">
                    <Icon size={20} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--c-100)]">{device.name}</h3>
                    <p className="text-xs text-[var(--c-500)]">{device.os}</p>
                  </div>
                </div>
                <StatusBadge status={device.status === 'online' ? 'online' : 'offline'} />
              </div>

              <div className="grid grid-cols-2 gap-2 mb-6 text-xs">
                <div className="bg-[var(--c-950-50)] p-2 rounded border border-[var(--c-800-50)]">
                  <span className="text-[var(--c-500)] block mb-1">IP 地址</span>
                  <span className="font-mono text-[var(--c-300)]">{device.ip}</span>
                </div>
                <div className="bg-[var(--c-950-50)] p-2 rounded border border-[var(--c-800-50)]">
                  <span className="text-[var(--c-500)] block mb-1">资源占用</span>
                  <span className="font-mono text-[var(--c-300)]">{device.cpu}% CPU</span>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleConnect(device.name, 'Desktop')}
                  disabled={device.status === 'offline'}
                  className="flex-1 bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] disabled:opacity-50 disabled:cursor-not-allowed py-2 rounded-lg text-sm font-medium transition-colors border border-[var(--c-700)] hover:border-[var(--c-600)]"
                >
                  远程桌面
                </button>
                <button
                  onClick={() => handleConnect(device.name, 'SSH')}
                  disabled={device.status === 'offline'}
                  className="px-4 bg-[var(--c-900)] hover:bg-[var(--c-800)] text-[var(--c-400)] hover:text-[var(--c-200)] border border-[var(--c-800)] hover:border-[var(--c-700)] rounded-lg transition-colors"
                >
                  <Terminal size={16} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default RemoteView;
