import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { isTauriRuntime } from '../../utils/tauriWindow';

type Preferences = { close_to_tray: boolean; tray_available: boolean };
export function DesktopSettings() {
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!isTauriRuntime()) return;
    let active = true;
    const unlisten = listen<Preferences>('desktop-preferences', event => { if (active) setPreferences(event.payload); });
    void invoke<Preferences>('desktop_preferences').then(value => { if (active) setPreferences(value); }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; void unlisten.then(stop => stop()).catch(() => undefined); };
  }, []);
  if (!isTauriRuntime()) return <p className="text-sm text-[var(--c-400)]">系统托盘仅在 R-Link 桌面版中可用。</p>;
  return <div className="space-y-4 text-sm">
    <label className="flex items-center justify-between gap-4">
      <span>关闭窗口后驻留系统托盘</span>
      <input type="checkbox" checked={preferences?.close_to_tray ?? false} disabled={!preferences?.tray_available || saving}
        onChange={async event => {
          const enabled = event.target.checked;
          setSaving(true); setError('');
          try { setPreferences(await invoke<Preferences>('set_close_to_tray', { enabled })); }
          catch (e) { setError(String(e)); }
          finally { setSaving(false); }
        }} />
    </label>
    <p className="text-[var(--c-500)]">隐藏窗口保留当前连接。单击托盘图标可恢复窗口；右键菜单可打开设备管理、SSH、设置，或退出 R-Link。</p>
    <p className="text-[var(--c-500)]">退出会断开本客户端终端连接；独立运行的服务端和网络插件继续运行。</p>
    {preferences && !preferences.tray_available && <p role="status">系统托盘不可用，关闭窗口将退出应用。</p>}
    {error && <p role="alert" className="text-red-400">{error}</p>}
  </div>;
}
