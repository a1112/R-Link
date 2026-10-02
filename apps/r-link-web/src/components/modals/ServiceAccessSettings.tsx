import { useState } from 'react';
import { apiOrigin, getServiceKey, setServiceKey } from '../../api/service-access';
import { getServiceUrl, setServiceUrl } from '../../api/service-url';

export function ServiceAccessSettings() {
  const [key, setKey] = useState(getServiceKey);
  const [address, setAddress] = useState(getServiceUrl);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const save = (value: string) => {
    setServiceKey(value);
    setKey(value);
    setSaved(true);
    window.dispatchEvent(new Event('r-link-service-access-changed'));
  };
  return <form className="space-y-4 max-w-xl" onSubmit={event => {
    event.preventDefault(); setError(''); setSaved(false);
    try { setServiceUrl(address); setAddress(getServiceUrl()); save(key); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }}>
    <p className="text-sm text-[var(--c-400)]">本机服务默认无需密钥。远程服务启用访问密钥时，在此填写；密钥仅保留在当前标签页。</p>
    <label className="block text-sm" htmlFor="service-api-url">服务地址</label>
    <input id="service-api-url" type="text" inputMode="url" autoComplete="url" value={address}
      placeholder="留空使用默认服务，或填写 https://rlink.example.com"
      onChange={event => { setAddress(event.target.value); setKey(''); setSaved(false); setError(''); }}
      className="w-full rounded-lg border border-[var(--c-700)] bg-[var(--c-900)] p-3" />
    <p className="text-xs text-[var(--c-500)]">当前服务：{apiOrigin()}。更换地址会刷新页面数据并关闭当前 SSH 会话；需要重新填写目标服务的密钥。</p>
    <label className="block text-sm" htmlFor="service-access-key">服务访问密钥</label>
    <input id="service-access-key" type="password" autoComplete="off" value={key}
      onChange={event => { setKey(event.target.value); setSaved(false); }}
      className="w-full rounded-lg border border-[var(--c-700)] bg-[var(--c-900)] p-3" />
    <div className="flex gap-3">
      <button type="submit" className="rounded-lg bg-[var(--c-200)] text-[var(--c-950)] px-4 py-2">保存连接</button>
      <button type="button" onClick={() => save('')} className="rounded-lg border border-[var(--c-700)] px-4 py-2">清除密钥</button>
    </div>
    {saved && <p role="status" className="text-sm text-emerald-400">已更新，页面请求将使用当前配置。</p>}
    {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
  </form>;
}
