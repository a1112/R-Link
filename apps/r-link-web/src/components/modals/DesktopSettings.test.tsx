import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn().mockResolvedValue(() => {}) }));
vi.mock('../../utils/tauriWindow', () => ({ isTauriRuntime: () => true }));
import { DesktopSettings } from './DesktopSettings';
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it('only hides through the native tray command when a tray is available', async () => {
  vi.mocked(invoke).mockResolvedValue({ close_to_tray: true, tray_available: true });
  render(<DesktopSettings />);
  const button = screen.getByRole('button', { name: '立即隐藏到托盘' });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  await waitFor(() => expect(invoke).toHaveBeenCalledWith('hide_to_tray'));
});
it('retains a visible window when native tray is unavailable', async () => {
  vi.mocked(invoke).mockResolvedValue({ close_to_tray: true, tray_available: false });
  render(<DesktopSettings />);
  expect(await screen.findByText('系统托盘不可用，关闭窗口将退出应用。')).toBeTruthy();
  expect((screen.getByRole('button', { name: '立即隐藏到托盘' }) as HTMLButtonElement).disabled).toBe(true);
});
