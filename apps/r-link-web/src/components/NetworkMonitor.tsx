import { useCallback, useEffect, useRef, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { http } from '../api/client';
import { usePolling } from '../api/usePolling';
import { defaultNetworkInterface, trafficRate, type NetworkSnapshot, type TrafficSample } from '../api/network';

const byteCount = (value: number) => {
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  const index = value > 0 ? Math.min(4, Math.floor(Math.log(value) / Math.log(1024))) : 0;
  return `${(value / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
};
const counter = (value?: number | null) => value == null ? '未知' : value.toLocaleString();

export function NetworkMonitor() {
  const { data, error, loading, refetch } = usePolling(useCallback((signal: AbortSignal) => http.get<NetworkSnapshot>('/api/system/network', { signal }), []), 5000);
  const [selected, setSelected] = useState('');
  const [history, setHistory] = useState<TrafficSample[]>([]);
  const previous = useRef<NetworkSnapshot | null>(null);
  const name = data?.interfaces.some(item => item.name === selected) ? selected : defaultNetworkInterface(data);
  const lastName = useRef(name);
  useEffect(() => {
    if (!data || lastName.current !== name) { previous.current = null; setHistory([]); }
    lastName.current = name;
    if (data) {
      const sample = trafficRate(previous.current, data, name);
      if (sample) setHistory(items => [...items.slice(-59), sample]);
      else setHistory([]);
      previous.current = data;
    }
  }, [data, name]);
  const iface = data?.interfaces.find(item => item.name === name);
  const rate = history[history.length - 1];
  return <section className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-6 lg:col-span-2">
    <div className="flex justify-between items-start gap-3 mb-4">
      <div><h3 className="font-semibold text-lg">服务端网络流量</h3><p className="text-sm text-[var(--c-500)]">{data?.hostname || '等待服务端'} · 每 5 秒采样，保留最近 60 个样本</p></div>
      <select aria-label="网络接口" className="bg-[var(--c-950)] rounded p-2 max-w-52" value={name} onChange={e => setSelected(e.target.value)}>
        {data?.interfaces.map(item => <option key={item.name} value={item.name}>{item.name}{item.is_up ? '' : '（未启用）'}</option>)}
      </select>
    </div>
    {error ? <p role="alert" className="text-red-400">无法获取网络状态：{error.message} <button onClick={() => void refetch()}>重试</button></p> : <>
      <p className="text-xs text-[var(--c-400)] break-all">{iface?.addresses.join(' · ') || (loading ? '加载中…' : '无接口地址')}</p>
      {iface && <>
        <dl className="grid grid-cols-2 xl:grid-cols-4 gap-3 mt-4 text-sm">
          <div><dt className="text-[var(--c-500)]">当前接收</dt><dd className="font-semibold mt-1">{rate ? `${rate.download.toFixed(2)} Mbps` : '等待采样'}</dd></div>
          <div><dt className="text-[var(--c-500)]">当前发送</dt><dd className="font-semibold mt-1">{rate ? `${rate.upload.toFixed(2)} Mbps` : '等待采样'}</dd></div>
          <div><dt className="text-[var(--c-500)]">接口累计接收</dt><dd className="font-semibold mt-1">{byteCount(iface.bytes_recv)}</dd></div>
          <div><dt className="text-[var(--c-500)]">接口累计发送</dt><dd className="font-semibold mt-1">{byteCount(iface.bytes_sent)}</dd></div>
        </dl>
        <p className="text-xs text-[var(--c-500)] mt-3">链路速率 {iface.link_speed_mbps && iface.link_speed_mbps > 0 ? `${iface.link_speed_mbps} Mbps` : '未知'} · MTU {counter(iface.mtu)} · 接收/发送包 {counter(iface.packets_recv)} / {counter(iface.packets_sent)}</p>
        <p className="text-xs text-[var(--c-500)] mt-1">累计接收/发送错误 {counter(iface.errin)} / {counter(iface.errout)} · 累计接收/发送丢包 {counter(iface.dropin)} / {counter(iface.dropout)}</p>
      </>}
      <div className="h-[260px] mt-3">
        {history.length < 2 ? <p className="text-sm text-[var(--c-500)]">{iface && !iface.is_up ? '接口未启用' : '等待连续采样以计算真实速率…'}</p> :
          <ResponsiveContainer width="100%" height="100%"><AreaChart data={history}>
            <XAxis dataKey="time" fontSize={10} /><YAxis fontSize={10} /><Tooltip />
            <Area type="linear" dataKey="download" name="接收 Mbps" stroke="#3b82f6" fill="#3b82f622" isAnimationActive={false} />
            <Area type="linear" dataKey="upload" name="发送 Mbps" stroke="#10b981" fill="#10b98122" isAnimationActive={false} />
          </AreaChart></ResponsiveContainer>}
      </div>
      {data && <p className="text-xs text-[var(--c-500)]">采样时间：{new Date(data.sampled_at * 1000).toLocaleTimeString()} · 所选接口流量，非设备间隧道流量</p>}
    </>}
  </section>;
}
