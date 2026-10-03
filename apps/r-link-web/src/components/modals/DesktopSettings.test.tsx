import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn().mockResolvedValue(() => {}) }));
vi.mock('../../utils/tauriWindow', () => ({ isTauriRuntime: () => true }));
import { DesktopSettings } from './DesktopSettings';
const preferences = (autostartEnabled: boolean | null = false) => ({
  close_to_tray: true, tray_available: true,
  autostart_enabled: autostartEnabled, autostart_error: null,
});
beforeEach(() => { vi.mocked(invoke).mockResolvedValue(preferences()); });
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.mocked(listen).mockResolvedValue(() => {}); });
it('only hides through the native tray command when a tray is available', async () => {
  vi.mocked(invoke).mockResolvedValue(preferences());
  render(<DesktopSettings />);
  const button = screen.getByRole('button', { name: '立即隐藏到托盘' });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  await waitFor(() => expect(invoke).toHaveBeenCalledWith('hide_to_tray'));
});
it('retains a visible window when native tray is unavailable', async () => {
  vi.mocked(invoke).mockResolvedValue({ ...preferences(), tray_available: false });
  render(<DesktopSettings />);
  expect(await screen.findByText('系统托盘不可用，关闭窗口将退出应用。')).toBeTruthy();
  expect((screen.getByRole('button', { name: '立即隐藏到托盘' }) as HTMLButtonElement).disabled).toBe(true);
});
it('shows the real enabled autostart state independently of tray availability and never enables on first render', async () => {
  vi.mocked(invoke).mockResolvedValue({ ...preferences(true), tray_available: false });
  render(<DesktopSettings />);
  const checkbox = await screen.findByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement;
  await waitFor(() => expect(checkbox.checked).toBe(true));
  expect(checkbox.disabled).toBe(false);
  expect(invoke).toHaveBeenCalledTimes(1);
  expect(invoke).toHaveBeenCalledWith('desktop_preferences');
});
it('locks desktop settings while startup changes and displays the OS result rather than an optimistic toggle', async () => {
  let finish!: (value: ReturnType<typeof preferences>) => void;
  const pending = new Promise<ReturnType<typeof preferences>>(resolve => { finish = resolve; });
  vi.mocked(invoke).mockImplementation(command => command === 'set_autostart' ? pending : Promise.resolve(preferences()));
  render(<DesktopSettings />);
  const checkbox = await screen.findByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement;
  await waitFor(() => expect(checkbox.disabled).toBe(false));
  fireEvent.click(checkbox);
  expect(checkbox.disabled).toBe(true);
  expect((screen.getByRole('checkbox', { name: '关闭窗口后驻留系统托盘' }) as HTMLInputElement).disabled).toBe(true);
  expect(invoke).toHaveBeenCalledWith('set_autostart', { enabled: true });
  await act(async () => { finish(preferences(false)); await pending; });
  await waitFor(() => expect(checkbox.disabled).toBe(false));
  expect(checkbox.checked).toBe(false);
});
it('shows startup failures and refreshes actual OS state without leaving an optimistic enabled checkbox', async () => {
  vi.mocked(invoke).mockImplementation(command => command === 'set_autostart'
    ? Promise.reject('系统拒绝开机自启写入') : Promise.resolve(preferences()));
  render(<DesktopSettings />);
  const checkbox = await screen.findByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement;
  await waitFor(() => expect(checkbox.disabled).toBe(false));
  fireEvent.click(checkbox);
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', '系统拒绝开机自启写入');
  await waitFor(() => expect(checkbox.disabled).toBe(false));
  expect(checkbox.checked).toBe(false);
  expect(vi.mocked(invoke).mock.calls.filter(([command]) => command === 'desktop_preferences')).toHaveLength(2);
});
it('reflects tray changes and ignores an older initial preferences response', async () => {
  let finish!: (value: ReturnType<typeof preferences>) => void;
  const pending = new Promise<ReturnType<typeof preferences>>(resolve => { finish = resolve; });
  vi.mocked(invoke).mockReturnValue(pending);
  render(<DesktopSettings />);
  await waitFor(() => expect(listen).toHaveBeenCalled());
  const onPreferences = vi.mocked(listen).mock.calls[0][1];
  await act(async () => { onPreferences({ event: 'desktop-preferences', id: 1, payload: preferences(true) }); });
  const checkbox = screen.getByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement;
  expect(checkbox.checked).toBe(true);
  await act(async () => { finish(preferences(false)); await pending; });
  expect(checkbox.checked).toBe(true);
});
it('refreshes startup state when returning to the application after an external OS change', async () => {
  render(<DesktopSettings />);
  const checkbox = await screen.findByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement;
  await waitFor(() => expect(checkbox.disabled).toBe(false));
  vi.mocked(invoke).mockResolvedValue(preferences(true));
  fireEvent.focus(window);
  await waitFor(() => expect(checkbox.checked).toBe(true));
});
it('reports an unreadable autostart state without presenting it as disabled or blocking tray preferences', async () => {
  vi.mocked(invoke).mockResolvedValue({ ...preferences(null), autostart_error: '无法读取登录启动配置' });
  render(<DesktopSettings />);
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', '无法读取登录启动配置');
  expect((screen.getByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByRole('checkbox', { name: '关闭窗口后驻留系统托盘' }) as HTMLInputElement).disabled).toBe(false);
});
it('clears a failed initial query after a successful refresh when the app regains focus', async () => {
  vi.mocked(invoke).mockRejectedValueOnce('桌面设置尚未初始化');
  render(<DesktopSettings />);
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', '桌面设置尚未初始化');
  fireEvent.focus(window);
  await waitFor(() => expect((screen.getByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement).disabled).toBe(false));
  expect(screen.queryByRole('alert')).toBeNull();
});
it('clears an obsolete query error when a successful native tray update supplies current state', async () => {
  vi.mocked(invoke).mockRejectedValueOnce('桌面设置尚未初始化');
  render(<DesktopSettings />);
  await screen.findByRole('alert');
  const onPreferences = vi.mocked(listen).mock.calls[0][1];
  await act(async () => { onPreferences({ event: 'desktop-preferences', id: 1, payload: preferences(true) }); });
  expect((screen.getByRole('checkbox', { name: '登录系统后自动启动 R-Link' }) as HTMLInputElement).checked).toBe(true);
  expect(screen.queryByRole('alert')).toBeNull();
});
