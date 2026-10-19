import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { bridgeProxyApi as api, BridgeProxyError, type BridgeAdapter, type BridgeTarget, type JsonObject } from '../../api/bridgeproxy';
import { resetAccount, updateAccount } from '../../api/account-access';
import BridgeProxyView, { newerVersion } from './BridgeProxyView';

vi.mock('../../api/bridgeproxy', async () => ({
  ...await vi.importActual('../../api/bridgeproxy'),
  bridgeProxyApi: { adapter: vi.fn(), connect: vi.fn(), disconnect: vi.fn(), request: vi.fn(), command: vi.fn() },
}));

const r1 = 'a'.repeat(64), r2 = 'b'.repeat(64);
let adapters: Record<BridgeTarget, BridgeAdapter>;
let replies: Record<BridgeTarget, Record<string, JsonObject>>;

function account(role: 'viewer' | 'admin', id: string = role) {
  updateAccount({ status: 'ready', config: { mode: 'oidc', login_enabled: true, desktop_login_enabled: true }, error: '', session: {
    mode: 'oidc', authenticated: true, user: { id, issuer: 'https://issuer.example', subject: id, display_name: id, email: null, role, disabled: false },
    csrf_token: 'csrf', session_context: 'session-' + id, expires_at: null,
  } });
}
function fixture(target: BridgeTarget): Record<string, JsonObject> {
  const instance = 'instance-' + target;
  const config = { name: target === 'server' ? 'Server Core' : 'Local Core', mixed_port: 17891, api_port: 17892,
    allow_lan: false, bypass_lan: true, final_action: 'proxy', upstream_link_id: null,
    outbound: { kind: 'socks5', host: 'upstream.example', port: 1080, username: 'owner', has_password: true, udp_over_tcp: false, custom_configured: false } };
  return {
    '/v1/snapshot': { age_ms: 0, instance_id: instance, generation: 1, published_at: Date.now(), resources: {
      '/v1/config': { revision: r1, config, dirty: false, unsaved_pairings: 0 },
      '/v1/rules': { revision: r1, rules: [{ enabled: true, kind: 'domain_suffix', value: 'example.test', action: 'proxy' }] },
      '/v1/status': { running: true, starting: false, tunnel_connected: false, tun_active: false, system_proxy_active: false, links: [] },
      '/v1/runtime': { running: true, saved_applied: true }, '/v1/nodes': { nodes: [] }, '/v1/links': { revision: r1, links: [] },
      '/v1/connections': { connections: [] }, '/v1/traffic': {}, '/v1/logs': { logs: [] },
      '/v1/diagnostics': { running: false, run_id: null, checks: [] }, '/v1/updates': { supported: true, phase: 'idle', ready: false },
    } },
    '/v1/capabilities': { manifest_version: 1, host: { instance_id: instance }, core: { id: 'bridgeproxy-core', version: '0.6.1' },
      routes: [{ method: 'POST', path: '/v1/updates/download', available: true }, { method: 'POST', path: '/v1/tokens/rotate', available: true }] },
    '/v1/operations': { instance_id: instance, operations: [] },
    '/v1/pairings/control': { window_open: true, pending: [{ id: 'pair_01', peer_name: 'Trusted peer', local_role: 'consumer', verification_code: '12345678', expires_in_secs: 100, local_approved: false, peer_approved: false }] },
  };
}
function resources(target: BridgeTarget = 'server') { return replies[target]['/v1/snapshot'].resources as Record<string, JsonObject>; }
async function mount() { await act(async () => { render(<BridgeProxyView />); }); }
async function tab(name: string) { await act(async () => { fireEvent.click(screen.getByRole('tab', { name })); }); }
const disabled = (name: string) => (screen.getByRole('button', { name }) as HTMLButtonElement).disabled;

beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); sessionStorage.clear(); resetAccount(); account('admin');
  delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
  adapters = {
    local: { configured: true, control_configured: true, target: 'local', endpoint_scope: 'desktop-loopback' },
    server: { configured: true, control_configured: true, target: 'server', endpoint_scope: 'server-loopback' },
  };
  replies = { local: fixture('local'), server: fixture('server') };
  vi.mocked(api.adapter).mockImplementation(async target => adapters[target]);
  vi.mocked(api.request).mockImplementation(async (target, request) => structuredClone(replies[target][request.path] ?? {}) as never);
  vi.mocked(api.command).mockResolvedValue({ queued: true });
  vi.mocked(api.disconnect).mockImplementation(async () => { adapters.local = { ...adapters.local, configured: false, control_configured: false }; });
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});
afterEach(() => { cleanup(); vi.useRealTimers(); resetAccount(); delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__; });

it('keeps an unconfigured server target unavailable without probing or inventing stopped state', async () => {
  adapters.server = { ...adapters.server, configured: false, control_configured: false };
  await mount();
  expect(api.request).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: '启动代理' })).toBeNull();
  expect(screen.queryByText('已停止')).toBeNull();
  expect(screen.getByText(/未连接不代表代理已停止/)).toBeTruthy();
});

it('offers viewers read-only resources without requesting SAS or enabling writes', async () => {
  account('viewer'); await mount();
  expect(disabled('启动代理')).toBe(true);
  await tab('发现与配对');
  expect(vi.mocked(api.request).mock.calls.some(([, request]) => request.path === '/v1/pairings/control')).toBe(false);
  expect(screen.queryByText('12345678')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '允许配对 2 分钟' }));
  expect(api.command).not.toHaveBeenCalled();
});

it('keeps an explicit local control grant independent from the server account role', async () => {
  Object.defineProperty(window, '__TAURI_INTERNALS__', { configurable: true, value: {} });
  account('viewer'); await mount();
  expect(disabled('启动代理')).toBe(false);
  await act(async () => { fireEvent.change(screen.getByLabelText('管理目标'), { target: { value: 'server' } }); });
  expect(disabled('启动代理')).toBe(true);
});

it('requires manual counterpart SAS input before approving a pairing', async () => {
  await mount(); await tab('发现与配对');
  expect(await screen.findByText('12345678')).toBeTruthy();
  const field = screen.getByLabelText('对端验证码 pair_01') as HTMLInputElement;
  expect(field.value).toBe(''); expect(disabled('验证码一致，确认配对')).toBe(true);
  expect(api.command).not.toHaveBeenCalled();
  fireEvent.change(field, { target: { value: '12345678' } });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '验证码一致，确认配对' })); });
  expect(api.command).toHaveBeenCalledWith('server', { method: 'POST', path: '/v1/pairings/pair_01/decision', body: { approve: true, verification_code: '12345678' } }, expect.any(AbortSignal));
});

it('submits rules and the final action in one revision-checked operation', async () => {
  await mount(); await tab('分流规则');
  fireEvent.change(screen.getByLabelText('规则动作 1'), { target: { value: 'direct' } });
  fireEvent.change(screen.getByLabelText('最终动作'), { target: { value: 'block' } });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '保存并应用分流规则' })); });
  expect(api.command).toHaveBeenCalledTimes(1);
  expect(api.command).toHaveBeenCalledWith('server', { method: 'PUT', path: '/v1/rules', revision: r1, body: {
    rules: [{ enabled: true, kind: 'domain_suffix', value: 'example.test', action: 'direct' }], final_action: 'block', apply: true,
  } }, expect.any(AbortSignal));
});

it('never writes an untouched redacted host or saved password while editing the node name', async () => {
  const cfg = resources()['/v1/config'].config as JsonObject;
  cfg.outbound = { ...(cfg.outbound as JsonObject), host: '[REDACTED]', username: '[REDACTED]' };
  await mount(); await tab('出口配置');
  fireEvent.change(screen.getByLabelText('节点名称'), { target: { value: 'New node name' } });
  await act(async () => { fireEvent.submit(screen.getByRole('button', { name: '保存并应用出口配置' }).closest('form')!); });
  expect(api.command).toHaveBeenCalledWith('server', { method: 'PATCH', path: '/v1/config', revision: r1,
    body: { name: 'New node name', apply: true } }, expect.any(AbortSignal));
});

it('clears a saved password only after the explicit clear option is selected', async () => {
  await mount(); await tab('出口配置');
  expect((screen.getByLabelText('新上游密码') as HTMLInputElement).value).toBe('');
  fireEvent.click(screen.getByLabelText('清除已保存上游密码'));
  await act(async () => { fireEvent.submit(screen.getByRole('button', { name: '保存并应用出口配置' }).closest('form')!); });
  expect(api.command).toHaveBeenCalledWith('server', { method: 'PATCH', path: '/v1/config', revision: r1,
    body: { outbound: { password: '' }, apply: true } }, expect.any(AbortSignal));
});

it('blocks replacing a redacted rule until the user explicitly supplies its value', async () => {
  (resources()['/v1/rules'].rules as JsonObject[])[0].value = '[REDACTED]';
  await mount(); await tab('分流规则');
  expect(disabled('保存并应用分流规则')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保存并应用分流规则' }));
  expect(api.command).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('规则内容 1'), { target: { value: 'reentered.example' } });
  expect(disabled('保存并应用分流规则')).toBe(false);
});

it('keeps the editing revision after polling detects another writer and preserves a conflicted draft', async () => {
  vi.useFakeTimers(); await mount(); await tab('出口配置');
  fireEvent.change(screen.getByLabelText('节点名称'), { target: { value: 'My pending edit' } });
  resources()['/v1/config'] = { revision: r2, config: { ...(resources()['/v1/config'].config as JsonObject), name: 'Other writer' } };
  resources()['/v1/rules'].revision = r2;
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect((screen.getByLabelText('节点名称') as HTMLInputElement).value).toBe('My pending edit');
  vi.mocked(api.command).mockRejectedValueOnce(new BridgeProxyError('配置已改变，请重新读取', 'revision_mismatch', 412));
  await act(async () => { fireEvent.submit(screen.getByRole('button', { name: '保存并应用出口配置' }).closest('form')!); });
  expect(api.command).toHaveBeenCalledWith('server', expect.objectContaining({ revision: r1, body: { name: 'My pending edit', apply: true } }), expect.any(AbortSignal));
  expect(screen.getByRole('alert').textContent).toContain('配置已改变');
  expect((screen.getByLabelText('节点名称') as HTMLInputElement).value).toBe('My pending edit');
});

it('rejects stale initial snapshots without showing a stopped core or allowing controls', async () => {
  replies.server['/v1/snapshot'].age_ms = 12001;
  await mount();
  expect(disabled('启动代理')).toBe(true);
  expect(screen.queryByText('已停止')).toBeNull();
  expect(screen.getByRole('alert').textContent).toContain('状态已过期');
});

it('uses the Core-reported age rather than comparing clocks on different machines', async () => {
  replies.server['/v1/snapshot'].published_at = Date.now() + 86400000;
  replies.server['/v1/snapshot'].age_ms = 500;
  await mount();
  expect(disabled('启动代理')).toBe(false);
  expect(screen.queryByRole('alert')).toBeNull();
});

it.each(['manifest', 'history'])('rejects a refresh assembled from different Core instances: %s', async source => {
  if (source === 'manifest') (replies.server['/v1/capabilities'].host as JsonObject).instance_id = 'another-instance';
  else replies.server['/v1/operations'].instance_id = 'another-instance';
  await mount();
  expect(disabled('启动代理')).toBe(true);
  expect(screen.getByRole('alert').textContent).toContain('Core 实例');
});

it('downgrades old running evidence when a later status poll fails', async () => {
  vi.useFakeTimers(); await mount();
  expect(disabled('启动代理')).toBe(false);
  vi.mocked(api.request).mockRejectedValue(new Error('Core disconnected'));
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(disabled('启动代理')).toBe(true);
  expect(screen.queryByText('运行中')).toBeNull();
  expect(screen.getByText(/Core disconnected/)).toBeTruthy();
});

it('does not install a late local poll into the selected server target', async () => {
  Object.defineProperty(window, '__TAURI_INTERNALS__', { configurable: true, value: {} });
  vi.useFakeTimers(); await mount();
  let complete!: (value: JsonObject) => void;
  const normal = vi.mocked(api.request).getMockImplementation()!;
  vi.mocked(api.request).mockImplementation((target, request, signal) => target === 'local' && request.path === '/v1/snapshot'
    ? new Promise(resolve => { complete = resolve; }) as never : normal(target, request, signal));
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  await act(async () => { fireEvent.change(screen.getByLabelText('管理目标'), { target: { value: 'server' } }); });
  await act(async () => { complete(structuredClone(replies.local['/v1/snapshot'])); });
  await tab('出口配置');
  expect((screen.getByLabelText('节点名称') as HTMLInputElement).value).toBe('Server Core');
});

it('asks before discarding an unsaved edit while changing targets or tabs', async () => {
  Object.defineProperty(window, '__TAURI_INTERNALS__', { configurable: true, value: {} });
  await mount(); await tab('出口配置');
  fireEvent.change(screen.getByLabelText('节点名称'), { target: { value: 'Keep my edit' } });
  vi.mocked(window.confirm).mockReturnValue(false);
  await tab('分流规则');
  expect((screen.getByLabelText('节点名称') as HTMLInputElement).value).toBe('Keep my edit');
  fireEvent.change(screen.getByLabelText('管理目标'), { target: { value: 'server' } });
  expect((screen.getByLabelText('管理目标') as HTMLSelectElement).value).toBe('local');
  expect(api.adapter).toHaveBeenCalledTimes(1);
});

it('clears secret drafts and native authority when the account identity changes', async () => {
  Object.defineProperty(window, '__TAURI_INTERNALS__', { configurable: true, value: {} });
  await mount(); await tab('出口配置');
  fireEvent.change(screen.getByLabelText('新上游密码'), { target: { value: 'private-old-account-password' } });
  await act(async () => { account('viewer', 'new-viewer'); });
  expect(api.disconnect).toHaveBeenCalledTimes(1);
  expect(screen.queryByDisplayValue('private-old-account-password')).toBeNull();
  expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
});

it('shows only strictly newer authenticated update offers and sends their exact link/hash', async () => {
  const offer = (version: string) => ({ product: 'bridgeproxy-windows', version, platform: 'windows-x86_64', size: 2048, sha256: 'f'.repeat(64) });
  resources()['/v1/status'].links = [
    { id: 'same', name: 'Same peer', connected: true, updates_supported: true, update_offer: offer('0.6.1') },
    { id: 'older', name: 'Older peer', connected: true, updates_supported: true, update_offer: offer('0.6.0') },
    { id: 'newer', name: 'New peer', connected: true, updates_supported: true, update_offer: offer('0.7.0') },
  ];
  await mount(); await tab('节点升级');
  const buttons = screen.getAllByRole('button', { name: '下载此节点新版' });
  expect(buttons).toHaveLength(1);
  expect(screen.queryByText(/Same peer|Older peer/)).toBeNull();
  await act(async () => { fireEvent.click(buttons[0]); });
  expect(api.command).toHaveBeenCalledWith('server', { method: 'POST', path: '/v1/updates/download', body: { link_id: 'newer', sha256: 'f'.repeat(64) } }, expect.any(AbortSignal));
});

it.each([
  ['0.10.0', '0.9.9', true], ['0.6.1', '0.6.1', false], ['0.6.0', '0.6.1', false],
  ['1.0.0-beta', '0.6.1', false], ['invalid', '0.6.1', false],
])('compares Core versions numerically: %s versus %s', (candidate, current, expected) => {
  expect(newerVersion(candidate, current)).toBe(expected);
});
