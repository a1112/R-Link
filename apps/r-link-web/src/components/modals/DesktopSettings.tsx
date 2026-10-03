import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { isTauriRuntime } from '../../utils/tauriWindow';

type Preferences = {
  close_to_tray: boolean;
  tray_available: boolean;
  autostart_enabled: boolean | null;
  autostart_error: string | null;
};
export function DesktopSettings() {
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const active = useRef(false);
  const version = useRef(0);
  const busy = useRef(false);
  const refreshPreferences = useCallback(async (preserveError = false) => {
    const requestVersion = ++version.current;
    try {
      const value = await invoke<Preferences>('desktop_preferences');
      if (active.current && requestVersion === version.current) {
        setPreferences(value);
        if (!preserveError) setError('');
      }
    } catch (e) {
      if (active.current && requestVersion === version.current) setError(String(e));
    }
  }, []);
  useEffect(() => {
    if (!isTauriRuntime()) return;
    active.current = true;
    const unlisten = listen<Preferences>('desktop-preferences', event => {
      if (active.current) {
        ++version.current; setPreferences(event.payload);
        if (!event.payload.autostart_error) setError('');
      }
    });
    void unlisten.catch(e => { if (active.current) setError(String(e)); });
    void refreshPreferences();
    const onFocus = () => { if (!busy.current) void refreshPreferences(); };
    window.addEventListener('focus', onFocus);
    return () => {
      active.current = false; ++version.current;
      window.removeEventListener('focus', onFocus);
      void unlisten.then(stop => stop()).catch(() => undefined);
    };
  }, [refreshPreferences]);
  const changePreference = async (command: 'set_close_to_tray' | 'set_autostart', enabled: boolean) => {
    if (busy.current) return;
    busy.current = true;
    const requestVersion = ++version.current;
    setSaving(true); setError('');
    try {
      const value = await invoke<Preferences>(command, { enabled });
      if (active.current && requestVersion === version.current) setPreferences(value);
    } catch (e) {
      if (active.current) { setError(String(e)); await refreshPreferences(true); }
    } finally {
      busy.current = false;
      if (active.current) setSaving(false);
    }
  };
  if (!isTauriRuntime()) return <p className="text-sm text-[var(--c-400)]">系统托盘仅在 R-Link 桌面版中可用。</p>;
  const displayedError = error || preferences?.autostart_error;
  return <div className="space-y-4 text-sm">
    <label className="flex items-center justify-between gap-4">
      <span>登录系统后自动启动 R-Link</span>
      <input type="checkbox" checked={preferences?.autostart_enabled ?? false}
        disabled={preferences?.autostart_enabled == null || saving}
        onChange={event => { void changePreference('set_autostart', event.target.checked); }} />
    </label>
    <p className="text-[var(--c-500)]">自启在当前用户登录后运行。系统托盘可用时自动驻留；托盘不可用时显示主窗口。再次打开 R-Link 可恢复窗口。</p>
    {preferences?.autostart_enabled == null && <p role="status">正在读取或无法确认系统自启状态。</p>}
    <label className="flex items-center justify-between gap-4">
      <span>关闭窗口后驻留系统托盘</span>
      <input type="checkbox" checked={preferences?.close_to_tray ?? false} disabled={!preferences?.tray_available || saving}
        onChange={event => { void changePreference('set_close_to_tray', event.target.checked); }} />
    </label>
    <p className="text-[var(--c-500)]">隐藏窗口保留当前连接。单击托盘图标可恢复窗口；右键菜单可打开仪表盘、设备管理、设备连接视图、SSH、共享文件、插件管理和设置，或退出 R-Link。</p>
    <button className="rounded border px-3 py-2" disabled={!preferences?.tray_available || saving} onClick={async () => {
      setError('');
      try { await invoke('hide_to_tray'); } catch (e) { setError(String(e)); }
    }}>立即隐藏到托盘</button>
    <p className="text-[var(--c-500)]">退出会断开本客户端终端连接；独立运行的服务端和网络插件继续运行。</p>
    {preferences && !preferences.tray_available && <p role="status">系统托盘不可用，关闭窗口将退出应用。</p>}
    {displayedError && <p role="alert" className="text-red-400">{displayedError}</p>}
  </div>;
}
