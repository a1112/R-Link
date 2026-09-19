/**
 * 设置弹窗组件
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Settings, Shield, Globe, Monitor, CheckCircle2 } from "lucide-react";
import { themes, getThemeStyles, type ThemeName } from "@/constants/theme";

export interface SettingsModalProps {
  /** 是否显示 */
  show: boolean;
  /** 关闭回调 */
  onClose: () => void;
  /** 当前主题 */
  currentTheme: ThemeName;
  /** 主题变更回调 */
  onThemeChange: (theme: ThemeName) => void;
}

type SettingsTab = 'general' | 'account' | 'network' | 'display';

const tabConfig: { id: SettingsTab; label: string; icon: React.ElementType }[] = [
  { id: "general", label: "通用设置", icon: Settings },
  { id: "account", label: "账户安全", icon: Shield },
  { id: "network", label: "网络配置", icon: Globe },
  { id: "display", label: "界面显示", icon: Monitor },
];

export const SettingsModal: React.FC<SettingsModalProps> = ({
  show,
  onClose,
  currentTheme,
  onThemeChange,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>("display");

  if (!show) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-8 backdrop-blur-sm"
      style={{ backgroundColor: 'var(--c-modal-overlay)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-3xl h-[520px] bg-[var(--c-950-85)] backdrop-blur-2xl border border-[var(--c-800)] rounded-2xl shadow-2xl overflow-hidden flex"
      >
        {/* Sidebar */}
        <div className="w-56 border-r border-[var(--c-800-50)] p-4 bg-[var(--c-900-50)]">
          <div className="mb-6 px-2">
            <h2 className="text-lg font-bold text-[var(--c-100)]">设置</h2>
          </div>
          <div className="space-y-1">
            {tabConfig.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-all ${
                  activeTab === tab.id
                    ? "bg-[var(--c-800)] text-[var(--c-100)] shadow-sm"
                    : "text-[var(--c-400)] hover:text-[var(--c-200)] hover:bg-[var(--c-800-50)]"
                }`}
              >
                <tab.icon size={16} />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="h-14 border-b border-[var(--c-800-50)] flex items-center justify-between px-8 shrink-0">
            <h3 className="font-semibold text-[var(--c-200)]">
              {tabConfig.find(t => t.id === activeTab)?.label}
            </h3>
            <button
              onClick={onClose}
              className="p-1.5 text-[var(--c-500)] hover:text-[var(--c-200)] hover:bg-[var(--c-800)] rounded-lg transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          <div className="flex-1 p-8 overflow-y-auto scrollbar-card">
            {activeTab === "general" && (
              <div className="space-y-6 max-w-xl">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-[var(--c-200)]">开机自启动</div>
                      <div className="text-xs text-[var(--c-500)]">系统启动时自动运行 R-Link</div>
                    </div>
                    <div className="w-10 h-5 bg-emerald-500 rounded-full relative cursor-pointer">
                      <div className="absolute right-1 top-1 w-3 h-3 bg-white rounded-full shadow-sm" />
                    </div>
                  </div>
                  <div className="w-full h-px bg-[var(--c-800-50)]" />
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-[var(--c-200)]">托盘图标</div>
                      <div className="text-xs text-[var(--c-500)]">关闭窗口时最小化到系统托盘</div>
                    </div>
                    <div className="w-10 h-5 bg-[var(--c-700)] rounded-full relative cursor-pointer">
                      <div className="absolute left-1 top-1 w-3 h-3 bg-[var(--c-400)] rounded-full shadow-sm" />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "account" && (
              <div className="space-y-6 max-w-xl">
                <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl divide-y divide-[var(--c-800)]">
                  <div className="p-4 flex items-center justify-between">
                    <div>
                      <div className="text-[var(--c-200)] font-medium text-sm">双重认证 (2FA)</div>
                      <div className="text-xs text-[var(--c-500)] mt-1">为您的管理账户添加额外的安全保护</div>
                    </div>
                    <div className="w-10 h-5 bg-[var(--c-800)] rounded-full relative cursor-pointer">
                      <div className="absolute left-1 top-1 w-3 h-3 bg-[var(--c-500)] rounded-full"></div>
                    </div>
                  </div>
                  <div className="p-4 flex items-center justify-between">
                    <div>
                      <div className="text-[var(--c-200)] font-medium text-sm">API 访问密钥</div>
                      <div className="text-xs text-[var(--c-500)] mt-1">管理用于自动化脚本的个人访问令牌</div>
                    </div>
                    <button className="text-xs font-medium bg-[var(--c-800)] text-[var(--c-300)] px-3 py-1.5 rounded-lg hover:bg-[var(--c-700)] transition-colors">管理密钥</button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "display" && (
              <div className="space-y-6">
                <div>
                  <h4 className="text-sm font-medium text-[var(--c-200)] mb-4">主题外观</h4>
                  <div className="grid grid-cols-2 gap-4">
                    {themes.map(theme => (
                      <div
                        key={theme.id}
                        onClick={() => onThemeChange(theme.id)}
                        className={`relative group cursor-pointer rounded-xl border-2 transition-all overflow-hidden ${currentTheme === theme.id ? 'border-[var(--c-200)] ring-1 ring-[var(--c-200)]/50' : 'border-[var(--c-800)] hover:border-[var(--c-700)]'}`}
                      >
                        <div className={`h-20 ${theme.bg} p-3 flex flex-col gap-2`}>
                          <div className="flex gap-2">
                            <div className={`w-2 h-2 rounded-full ${theme.primary}`} />
                            <div className="w-12 h-2 rounded-full bg-white/10" />
                          </div>
                          <div className="space-y-1 mt-auto opacity-50">
                            <div className="w-full h-1 rounded-full bg-white/10" />
                            <div className="w-2/3 h-1 rounded-full bg-white/10" />
                          </div>
                        </div>
                        <div className="p-3 bg-[var(--c-900-50)] flex items-center justify-between border-t border-[var(--c-800-50)]">
                          <span className={`text-xs font-medium ${currentTheme === theme.id ? 'text-[var(--c-100)]' : 'text-[var(--c-500)]'}`}>{theme.name}</span>
                          {currentTheme === theme.id && <CheckCircle2 size={14} className="text-[var(--c-100)]" />}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-4 pt-4 border-t border-[var(--c-800-50)]">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-[var(--c-200)]">界面缩放</div>
                      <div className="text-xs text-[var(--c-500)]">调整应用程序的显示比例</div>
                    </div>
                    <select className="bg-[var(--c-900)] border border-[var(--c-800)] text-[var(--c-300)] text-xs rounded-lg px-2 py-1 outline-none focus:border-[var(--c-700)]">
                      <option>100%</option>
                      <option>110%</option>
                      <option>125%</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "network" && (
              <div className="flex flex-col items-center justify-center h-full text-[var(--c-500)] space-y-4">
                <div className="w-16 h-16 rounded-full bg-[var(--c-800-50)] flex items-center justify-center">
                  <Globe size={32} className="opacity-20" />
                </div>
                <p className="text-sm">该模块配置项正在开发中...</p>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default SettingsModal;
