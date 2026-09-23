import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { pluginsApi } from '../api/plugins';
vi.mock('../api/plugins', () => ({ pluginsApi: { getLogs: vi.fn(), getConfig: vi.fn(), setConfig: vi.fn() } }));
import { PluginDetailModal } from './PluginDetailModal';
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const plugin = { name: 'actual', description: 'Actual plugin', version: '3', author: 'Owner' };
it('displays the server log string rather than fabricated release notes', async () => {
  vi.mocked(pluginsApi.getLogs).mockResolvedValue({ plugin: 'actual', lines: 100, logs: 'first real line\nsecond real line' });
  render(<PluginDetailModal plugin={plugin} onClose={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: '运行日志' }));
  expect(await screen.findByText(/first real line/)).toBeTruthy();
  expect(screen.queryByText('2023-10-25')).toBeNull();
});
it('saves real JSON config and shows backend failures without a success message', async () => {
  vi.mocked(pluginsApi.getConfig).mockResolvedValue({ port: 1234 });
  vi.mocked(pluginsApi.setConfig).mockRejectedValue(new Error('Stop the console first'));
  render(<PluginDetailModal plugin={plugin} onClose={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: '配置' }));
  const input = await screen.findByLabelText('插件配置（JSON）');
  fireEvent.change(input, { target: { value: '{"port":4321}' } });
  fireEvent.click(screen.getByRole('button', { name: '保存配置' }));
  await waitFor(() => expect(pluginsApi.setConfig).toHaveBeenCalledWith('actual', { port: 4321 }));
  expect((await screen.findByRole('alert')).textContent).toContain('Stop the console first');
  expect(screen.queryByText(/配置已保存/)).toBeNull();
});
