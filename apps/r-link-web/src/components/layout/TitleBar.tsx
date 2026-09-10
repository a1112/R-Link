/**
 * 窗口标题栏组件
 * 支持拖拽、最小化、最大化、关闭功能
 */

import React, { useState, useEffect } from "react";
import { Minus, Maximize2, X } from "lucide-react";
import {
  isTauriRuntime,
  isElectronRuntime,
  isDesktopRuntime,
  withTauriWindow,
} from "../../utils/tauriWindow";

export interface TitleBarProps {
  title?: string;
  version?: string;
  showMenu?: boolean;
  children?: React.ReactNode;
}

export const TitleBar: React.FC<TitleBarProps> = ({
  title = "R-Link",
  version = "0.1.0",
  showMenu = true,
  children,
}) => {
  const isElectron = isElectronRuntime();
  const isTauri = isTauriRuntime();
  const canDrag = isDesktopRuntime();
  const useElectronDragRegion = isElectron;
  const hasWindowControls = isDesktopRuntime();

  const [isMaximized, setIsMaximized] = useState(false);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(() => {
    const raw = window.localStorage.getItem("auth_user");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  });

  // 初始化最大化状态
  useEffect(() => {
    if (!isElectron || !(window as any).electronWindow?.isMaximized) return;
    (window as any)
      .electronWindow.isMaximized()
      .then(setIsMaximized)
      .catch(() => undefined);
  }, [isElectron]);

  // Tauri 拖拽开始
  const handleTauriDragStart = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!isTauri || event.button !== 0) return;
    if (event.detail > 1) return;
    const target = event.target as HTMLElement | null;
    if (
      target?.closest(
        'button, a, input, select, textarea, [role="button"], [role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"], [data-radix-collection-item], [data-no-drag="true"]',
      )
    ) {
      return;
    }
    event.preventDefault();
    void withTauriWindow((appWindow) => appWindow.startDragging());
  };

  // 双击切换最大化
  const handleDragDoubleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null;
    if (
      target?.closest(
        'button, a, input, select, textarea, [role="button"], [role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"], [data-radix-collection-item], [data-no-drag="true"]',
      )
    ) {
      return;
    }
    event.preventDefault();
    void handleToggleMaximize();
  };

  // 最小化
  const handleMinimize = () => {
    if (isElectron) {
      (window as any).electronWindow?.minimize?.();
      return;
    }
    void withTauriWindow((appWindow) => appWindow.minimize());
  };

  // 切换最大化
  const handleToggleMaximize = async () => {
    if (isElectron) {
      const next = await (window as any).electronWindow?.toggleMaximize?.();
      if (typeof next === "boolean") setIsMaximized(next);
      return;
    }
    await withTauriWindow(async (appWindow) => {
      await appWindow.toggleMaximize();
      const next = await appWindow.isMaximized();
      if (typeof next === "boolean") setIsMaximized(next);
    });
  };

  // 关闭
  const handleClose = () => {
    if (isElectron) {
      (window as any).electronWindow?.close?.();
      return;
    }
    void withTauriWindow((appWindow) => appWindow.close());
  };

  return (
    <div
      className={`h-10 bg-[var(--c-900)]/80 backdrop-blur-md border-b border-[var(--c-800)] flex items-center justify-between px-4 select-none shrink-0 z-50 ${useElectronDragRegion ? "electron-drag" : ""}`}
      onMouseDown={handleTauriDragStart}
      onDoubleClick={handleDragDoubleClick}
      data-tauri-drag-region
    >
      {/* Left: Icon and Title */}
      <div className={`flex items-center gap-3 ${canDrag ? "electron-no-drag" : ""}`}>
        {/* Logo Icon */}
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">R</span>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-medium text-[var(--c-100)]">{title}</span>
            <span className="text-[10px] text-[var(--c-500)]">{version}</span>
          </div>
        </div>

        {showMenu && (
          <>
            <div className="w-px h-4 bg-[var(--c-800)]"></div>
            {/* Menu Button */}
            <button className="p-1 hover:bg-[var(--c-800)] text-[var(--c-400)] hover:text-[var(--c-100)] rounded transition-colors">
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
          </>
        )}
      </div>

      {/* Center: Custom Content */}
      <div className={`flex-1 flex items-center justify-center ${canDrag ? "electron-no-drag" : ""}`}>
        {children}
      </div>

      {/* Right: Window Controls */}
      <div className={`flex items-center gap-1 ${canDrag ? "electron-no-drag" : ""}`}>
        {/* Window Controls - 仅桌面版显示 */}
        <div className={hasWindowControls ? "flex items-center" : "hidden"}>
          {/* 最小化 */}
          <button
            className="p-1.5 hover:bg-[var(--c-800)] text-[var(--c-400)] hover:text-[var(--c-100)] rounded transition-colors"
            onClick={handleMinimize}
            title="最小化"
          >
            <Minus className="w-4 h-4" />
          </button>

          {/* 最大化/还原 */}
          <button
            className="p-1.5 hover:bg-[var(--c-800)] text-[var(--c-400)] hover:text-[var(--c-100)] rounded transition-colors"
            onClick={handleToggleMaximize}
            title={isMaximized ? "还原" : "最大化"}
          >
            {isMaximized ? (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
                />
              </svg>
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>

          {/* 关闭 */}
          <button
            className="p-1.5 hover:bg-red-600/80 text-[var(--c-400)] hover:text-white rounded transition-colors"
            onClick={handleClose}
            title="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
