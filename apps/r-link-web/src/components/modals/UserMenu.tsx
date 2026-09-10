/**
 * 用户菜单弹窗组件
 */

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { User, CreditCard, Settings, LogOut, FileText } from "lucide-react";

export interface UserMenuProps {
  /** 是否显示 */
  show: boolean;
  /** 关闭回调 */
  onClose: () => void;
  /** 打开设置回调 */
  onOpenSettings: () => void;
  /** 打开用户协议回调 */
  onOpenTerms?: () => void;
  /** 退出登录回调 */
  onLogout: () => void;
  /** 是否游客模式 */
  isGuest?: boolean;
  /** 用户信息 */
  userInfo?: {
    name?: string;
    email?: string;
    avatar?: string;
  };
}

export const UserMenu: React.FC<UserMenuProps> = ({
  show,
  onClose,
  onOpenSettings,
  onOpenTerms,
  onLogout,
  isGuest = false,
  userInfo = {},
}) => {
  const defaultName = isGuest ? 'Guest' : 'Admin User';
  const defaultEmail = isGuest ? 'guest@r-link.net' : 'admin@r-link.net';
  const avatar = userInfo.avatar || (isGuest ? '' : 'RL');

  return (
    <AnimatePresence>
      {show && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-transparent"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.1 }}
            className="absolute top-12 right-4 w-64 bg-[var(--c-950-80)] backdrop-blur-xl border border-[var(--c-800)] rounded-xl shadow-2xl z-50 overflow-hidden"
          >
            <div className="p-4 border-b border-[var(--c-800-50)]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[var(--c-800)] border border-[var(--c-700)] flex items-center justify-center text-sm font-medium text-[var(--c-300)]">
                  {avatar || <User size={18} />}
                </div>
                <div>
                  <div className="text-sm font-medium text-[var(--c-100)]">{userInfo.name || defaultName}</div>
                  <div className="text-xs text-[var(--c-500)]">{userInfo.email || defaultEmail}</div>
                </div>
              </div>
            </div>

            <div className="p-2 space-y-1">
              <button className="w-full flex items-center gap-3 px-3 py-2 text-sm text-[var(--c-400)] hover:text-[var(--c-100)] hover:bg-[var(--c-800-50)] rounded-lg transition-colors group">
                <User size={16} className="text-[var(--c-500)] group-hover:text-[var(--c-100)]" />
                个人资料
              </button>
              <button className="w-full flex items-center gap-3 px-3 py-2 text-sm text-[var(--c-400)] hover:text-[var(--c-100)] hover:bg-[var(--c-800-50)] rounded-lg transition-colors group">
                <CreditCard size={16} className="text-[var(--c-500)] group-hover:text-[var(--c-100)]" />
                订阅管理
              </button>
              {onOpenTerms && (
                <button
                  onClick={() => {
                    onClose();
                    onOpenTerms();
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2 text-sm text-[var(--c-400)] hover:text-[var(--c-100)] hover:bg-[var(--c-800-50)] rounded-lg transition-colors group"
                >
                  <FileText size={16} className="text-[var(--c-500)] group-hover:text-[var(--c-100)]" />
                  用户协议与隐私
                </button>
              )}
              <button
                onClick={() => {
                  onClose();
                  onOpenSettings();
                }}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-[var(--c-400)] hover:text-[var(--c-100)] hover:bg-[var(--c-800-50)] rounded-lg transition-colors group"
              >
                <Settings size={16} className="text-[var(--c-500)] group-hover:text-[var(--c-100)]" />
                系统设置
              </button>
            </div>

            <div className="p-2 border-t border-[var(--c-800-50)]">
              <button
                onClick={() => {
                  onClose();
                  onLogout();
                }}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              >
                <LogOut size={16} />
                退出登录
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default UserMenu;
