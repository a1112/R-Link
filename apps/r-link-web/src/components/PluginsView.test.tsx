import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ start: vi.fn(), stop: vi.fn(), restart: vi.fn(), refetch: vi.fn() }));
vi.mock('../api/hooks', () => ({
  usePlugins: () => ({ data: [{ name: 'demo', version: '1', description: 'Demo', author: 'test', status: { status: 'running', cpu_usage: 1 } }], refetch: mocks.refetch }),
  usePluginActions: () => mocks,
}));
vi.mock('../api/client', () => ({ http: { delete: vi.fn() } }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
import { PluginsView } from './PluginsView';
afterEach(cleanup);

it('restarts a running plugin without calling stop or opening its details', async () => {
  render(<PluginsView />);
  fireEvent.click(screen.getByRole('button', { name: '重启 demo' }));
  await waitFor(() => expect(mocks.restart).toHaveBeenCalledWith('demo'));
  expect(mocks.stop).not.toHaveBeenCalled();
  expect(mocks.start).not.toHaveBeenCalled();
  expect(screen.queryByText('卸载')).toBeNull();
});
