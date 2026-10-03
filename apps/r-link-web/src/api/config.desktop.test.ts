import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const invoke = vi.hoisted(() => vi.fn());
vi.mock('@tauri-apps/api/core', () => ({ invoke }));

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  invoke.mockReset();
});

afterEach(() => {
  delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
});

it('uses the owned desktop endpoint when the conventional port is occupied', async () => {
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
  invoke.mockResolvedValue('http://127.0.0.1:54321');
  const { API_CONFIG, initializeDesktopBackend } = await import('./config');
  await initializeDesktopBackend();
  expect(invoke).toHaveBeenCalledWith('desktop_backend_endpoint');
  expect(API_CONFIG.baseURL).toBe('http://127.0.0.1:54321');
});

it('retains an explicitly selected remote service', async () => {
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
  invoke.mockResolvedValue('http://127.0.0.1:54321');
  localStorage.setItem('r-link-service-url', 'https://managed.example.com');
  const { API_CONFIG, initializeDesktopBackend } = await import('./config');
  await initializeDesktopBackend();
  expect(API_CONFIG.baseURL).toBe('https://managed.example.com');
});

it('does not invoke native IPC from the web client', async () => {
  const { initializeDesktopBackend } = await import('./config');
  await initializeDesktopBackend();
  expect(invoke).not.toHaveBeenCalled();
});
