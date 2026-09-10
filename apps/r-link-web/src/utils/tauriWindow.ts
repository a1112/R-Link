/**
 * Tauri 窗口工具类
 * 支持 Tauri v2 窗口操作
 * 在非 Tauri 环境中安全跳过
 */

export type TauriWindowLike = {
  startDragging: () => Promise<void> | void;
  minimize: () => Promise<void> | void;
  toggleMaximize: () => Promise<void> | void;
  maximize: () => Promise<void> | void;
  unmaximize: () => Promise<void> | void;
  isMaximized: () => Promise<boolean> | boolean;
  close: () => Promise<void> | void;
};

/**
 * 检测是否在 Tauri 环境中运行
 */
export const isTauriRuntime = (): boolean => {
  if (typeof window === "undefined") return false;
  const w = window as any;
  return !!(w.__TAURI__ || w.__TAURI_INTERNALS__);
};

/**
 * 检测是否在 Electron 环境中运行
 */
export const isElectronRuntime = (): boolean => {
  if (typeof window === "undefined") return false;
  const w = window as any;
  return !!(w.electronWindow || w.process?.versions?.electron);
};

/**
 * 检测是否在桌面环境中运行
 */
export const isDesktopRuntime = (): boolean => {
  return isTauriRuntime() || isElectronRuntime();
};

/**
 * 获取 Tauri 窗口实例（仅在 Tauri 环境中有效）
 */
const getTauriWindow = async (): Promise<TauriWindowLike | null> => {
  if (typeof window === "undefined") return null;

  // 快速检测：如果不是 Tauri 环境，直接返回 null
  if (!isTauriRuntime()) return null;

  const w = window as any;
  const tauri = w.__TAURI__;

  // Tauri v2 API
  if (tauri?.webviewWindow?.getCurrentWebviewWindow) {
    return tauri.webviewWindow.getCurrentWebviewWindow();
  }
  if (tauri?.window?.getCurrentWindow) {
    return tauri.window.getCurrentWindow();
  }

  // Tauri v2 内部 API
  const internals = w.__TAURI_INTERNALS__;
  const currentLabel = internals?.metadata?.currentWindow?.label;
  if (internals?.invoke && currentLabel) {
    const invokeWindow = (command: string) =>
      internals.invoke(`plugin:window|${command}`, {
        label: currentLabel,
      });
    return {
      startDragging: () => invokeWindow("start_dragging"),
      minimize: () => invokeWindow("minimize"),
      toggleMaximize: () => invokeWindow("toggle_maximize"),
      maximize: () => invokeWindow("maximize"),
      unmaximize: () => invokeWindow("unmaximize"),
      isMaximized: () => invokeWindow("is_maximized"),
      close: () => invokeWindow("close"),
    };
  }

  // 如果到达这里，说明 Tauri API 不可用
  return null;
};

/**
 * 执行窗口操作（仅在 Tauri 环境中执行）
 */
export const withTauriWindow = async (
  action: (appWindow: TauriWindowLike) => Promise<void> | void,
): Promise<void> => {
  const win = await getTauriWindow();
  if (!win) return;
  await action(win);
};

/**
 * 同步版本的窗口操作（使用全局 API）
 */
export const withTauriWindowSync = (
  action: (appWindow: TauriWindowLike) => void,
): void => {
  if (typeof window === "undefined") return;
  if (!isTauriRuntime()) return;

  const w = window as any;
  const tauri = w.__TAURI__;

  let appWindow: TauriWindowLike | null = null;

  if (tauri?.webviewWindow?.getCurrentWebviewWindow) {
    appWindow = tauri.webviewWindow.getCurrentWebviewWindow();
  } else if (tauri?.window?.getCurrentWindow) {
    appWindow = tauri.window.getCurrentWindow();
  }

  if (appWindow) {
    action(appWindow);
  }
};
