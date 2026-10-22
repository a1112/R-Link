import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { fabricApi, getNativeFabricStatus, type FabricPeer, type FabricStatus } from '../../api/fabric';
import { resetAccount, updateAccount } from '../../api/account-access';
import { FabricView } from './FabricView';

vi.mock('../../api/fabric', async () => ({ ...await vi.importActual('../../api/fabric'), fabricApi: { status: vi.fn(), peers: vi.fn(), groups: vi.fn(), enrollments: vi.fn(), createEnrollment: vi.fn(), revokeEnrollment: vi.fn() }, getNativeFabricStatus: vi.fn() }));
const status: FabricStatus = { schema_version: 1, provider: 'rlink', configured: true, control_url: 'https://cloud.example/r-link', peers: 1, connected: 1, config_version: 1, mode: 'direct+relay', mode_transport: 'transport-test', capabilities: { enrollment: true, revocation: true, groups: true, p2p: true, relay: true, policies: false, networks: false, vpn: false } };
const peer = (): FabricPeer => ({ id: 'peer-a', peer_id: 'peer-a', name: 'Mac Air', os: 'macos', ip: '10.66.0.2', public_key: 'public-key', groups: [{ id: 'rlink-devices', name: 'R-Link devices' }], mode: 'transport-test', connected: true, control_connected: true, relay_connected: true, tunnel_ready_reported: false, data_plane_confirmed: false, last_seen: Date.now() / 1000, paths: [{ peer_id: 'peer-b', path: 'direct', last_handshake: null, reported_at: Date.now() / 1000, rtt_ms: 12 }] });
function account(role: 'viewer' | 'admin') {
  updateAccount({ status: 'ready', config: { mode: 'oidc', login_enabled: true, desktop_login_enabled: true }, error: '', session: { mode: 'oidc', authenticated: true, user: { id: 'user', issuer: 'https://issuer.example', subject: 'sub', display_name: 'User', email: null, role, disabled: false }, csrf_token: 'csrf', session_context: 'context', expires_at: null } });
}
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear(); resetAccount(); account('viewer');
  vi.mocked(fabricApi.status).mockResolvedValue(status); vi.mocked(fabricApi.peers).mockResolvedValue([peer()]);
  vi.mocked(fabricApi.groups).mockResolvedValue([{ id: 'rlink-devices', name: 'R-Link devices' }]);
  vi.mocked(fabricApi.enrollments).mockResolvedValue([]); vi.mocked(getNativeFabricStatus).mockResolvedValue(null);
});
afterEach(() => { cleanup(); resetAccount(); });

it('shows honest transport and path states to viewers without requesting admin metadata', async () => {
  render(<FabricView canManage={false} />); await screen.findByText('Mac Air');
  expect(screen.getByText('传输测试 · 非 VPN')).toBeTruthy();
  expect(screen.queryByText('近期 VPN 握手已确认')).toBeNull();
  expect(screen.getByText(/RTT 12.0 ms/)).toBeTruthy();
  expect(fabricApi.enrollments).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: '生成一次性入网凭据' })).toBeNull();
  expect(screen.queryByRole('button', { name: /策略|路由/ })).toBeNull();
});

it('does not label a working native transport probe as a ready system TUN', async () => {
  vi.mocked(getNativeFabricStatus).mockResolvedValue({ schema_version: 1, provider: 'rlink-fabric', device_id: 'local', name: 'This Mac', control_url: 'https://cloud.example/r-link', control: { connected: true, last_success_at: Date.now() / 1000 }, tun: { ready: false, name: null, ip: null }, peers: [], updated_at: Date.now() / 1000, mode: 'transport-test' });
  render(<FabricView />); await screen.findByText('Mac Air');
  expect(screen.getByText(/尚未建立系统虚拟网卡/)).toBeTruthy();
  expect(screen.getByText('系统 TUN：未确认就绪')).toBeTruthy();
});

it('reports a known native startup failure without describing an absent Agent or a ready VPN', async () => {
  vi.mocked(getNativeFabricStatus).mockResolvedValue({ schema_version: 1, provider: 'rlink-fabric', device_id: 'local', name: 'This Windows PC', control_url: 'https://cloud.example/r-link', control: { connected: true, last_success_at: Date.now() / 1000 }, tun: { ready: true, name: 'RLink', ip: '10.66.0.2' }, peers: [], updated_at: Date.now() / 1000, mode: 'vpn', status_error: 'startup_failed' });
  render(<FabricView />); await screen.findByText('Mac Air');
  expect(screen.getByText('组网服务启动失败，请查看本机安装结果。')).toBeTruthy();
  expect(screen.queryByText(/未读取到本机 Agent/)).toBeNull();
  expect(screen.getByText('系统 TUN：未确认就绪')).toBeTruthy();
  expect(screen.queryByText('近期 VPN 握手已确认')).toBeNull();
});

it('does not trust stale heartbeats or a transport-test data_plane_confirmed flag', async () => {
  vi.mocked(fabricApi.peers).mockResolvedValue([{ ...peer(), mode: 'vpn', tunnel_ready_reported: true, data_plane_confirmed: true, last_seen: 1 }]);
  render(<FabricView />); await screen.findByText('Mac Air');
  expect(screen.getByText('VPN 数据面待确认')).toBeTruthy(); expect(screen.queryByText('近期 VPN 握手已确认')).toBeNull();
});

it('marks VPN as confirmed only with a fresh mode-vpn TUN and a reported real handshake', async () => {
  vi.mocked(fabricApi.peers).mockResolvedValue([{ ...peer(), mode: 'vpn', tunnel_ready_reported: true, data_plane_confirmed: true, paths: [{ peer_id: 'peer-b', path: 'relay', last_handshake: Date.now() / 1000, reported_at: Date.now() / 1000, rtt_ms: 20 }] }]);
  render(<FabricView />); await screen.findByText('Mac Air');
  expect(screen.getByText('近期 VPN 握手已确认')).toBeTruthy();
  expect(screen.getByText(/至 peer-b：中转/)).toBeTruthy();
});

it('shows the enrollment token once only in memory and clears it on account downgrade', async () => {
  account('admin');
  vi.mocked(fabricApi.createEnrollment).mockResolvedValue({ id: 'enroll-a', name: 'Mac Air', enrollment_token: 'once-only-secret', expires_at: Date.now() / 1000 + 3600, groups: ['rlink-devices'], uses: 1, used: 0 });
  render(<FabricView canManage />); await screen.findByText('Mac Air');
  fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'Mac Air' } });
  fireEvent.click(screen.getByRole('button', { name: '生成一次性入网凭据' }));
  expect(await screen.findByText('once-only-secret')).toBeTruthy();
  expect(fabricApi.createEnrollment).toHaveBeenCalledWith({ name: 'Mac Air', groups: ['rlink-devices'], ttl_seconds: 3600 }, expect.any(AbortSignal));
  expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  act(() => account('viewer'));
  await waitFor(() => expect(screen.queryByText('once-only-secret')).toBeNull());
  expect(screen.queryByRole('button', { name: '生成一次性入网凭据' })).toBeNull();
});

it('discards a late enrollment result after the identity changes', async () => {
  account('admin'); let complete!: (value: Awaited<ReturnType<typeof fabricApi.createEnrollment>>) => void;
  vi.mocked(fabricApi.createEnrollment).mockImplementation(() => new Promise(resolve => { complete = resolve; }));
  render(<FabricView canManage />); await screen.findByText('Mac Air');
  fireEvent.change(screen.getByLabelText('设备名称'), { target: { value: 'Mac Air' } }); fireEvent.click(screen.getByRole('button', { name: '生成一次性入网凭据' }));
  act(() => account('viewer'));
  await act(async () => { complete({ id: 'enroll-a', name: 'Mac Air', enrollment_token: 'old-secret', expires_at: Date.now() / 1000 + 3600, groups: ['rlink-devices'], uses: 1, used: 0 }); });
  expect(screen.queryByText('old-secret')).toBeNull();
});
