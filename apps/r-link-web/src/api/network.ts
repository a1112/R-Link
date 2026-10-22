export type NetworkInterface = {
  name: string; is_up: boolean; addresses: string[]; bytes_sent: number; bytes_recv: number;
  packets_sent?: number | null; packets_recv?: number | null;
  errin?: number | null; errout?: number | null; dropin?: number | null; dropout?: number | null;
  link_speed_mbps?: number | null; mtu?: number | null;
};
export type NetworkSnapshot = { hostname: string; sampled_at: number; boot_time: number; interfaces: NetworkInterface[] };
export type TrafficSample = { time: string; upload: number; download: number };
export function defaultNetworkInterface(snapshot: NetworkSnapshot | null): string {
  const interfaces = snapshot?.interfaces ?? [];
  return interfaces.find(item => item.is_up && !/^lo\d*$/i.test(item.name) && item.addresses.some(address => {
    const value = address.toLowerCase().split('%')[0];
    return !value.startsWith('127.') && !value.startsWith('169.254.') && value !== '::1' && !value.startsWith('fe80:') && !value.startsWith('::ffff:127.');
  }))?.name || interfaces.find(item => item.is_up && !/^lo\d*$/i.test(item.name))?.name || interfaces[0]?.name || '';
}
export function trafficRate(previous: NetworkSnapshot | null, current: NetworkSnapshot, name: string): TrafficSample | null {
  const before = previous?.interfaces.find(item => item.name === name);
  const after = current.interfaces.find(item => item.name === name);
  const elapsed = current.sampled_at - (previous?.sampled_at ?? current.sampled_at);
  if (!before || !after || !after.is_up || !before.is_up || previous?.boot_time !== current.boot_time || !Number.isFinite(elapsed) || elapsed <= 0 || elapsed > 30) return null;
  const sent = after.bytes_sent - before.bytes_sent;
  const received = after.bytes_recv - before.bytes_recv;
  if (!Number.isFinite(sent) || !Number.isFinite(received) || sent < 0 || received < 0) return null;
  return { time: new Date(current.sampled_at * 1000).toLocaleTimeString(), upload: sent * 8 / elapsed / 1e6, download: received * 8 / elapsed / 1e6 };
}
