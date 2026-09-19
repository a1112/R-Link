import { useState } from 'react';
import { apiOrigin, getServiceKey, setServiceKey } from '../../api/service-access';

export function ServiceAccessSettings() {
  const [key, setKey] = useState(getServiceKey);
  const [saved, setSaved] = useState(false);
  const save = (value: string) => {
    setServiceKey(value);
    setKey(value);
    setSaved(true);
    window.dispatchEvent(new Event('r-link-service-access-changed'));
  };
  return <form className="space-y-4 max-w-xl" onSubmit={event => { event.preventDefault(); save(key); }}>
    <p className="text-sm text-[var(--c-400)]">本机服务默认无需密钥。远程服务启用访问密钥时，在此填写；密钥仅保留在当前标签页。</p>
    <p className="text-xs text-[var(--c-500)]">服务地址：{apiOrigin()}</p>
    <label className="block text-sm" htmlFor="service-access-key">服务访问密钥</label>
    <input id="service-access-key" type="password" autoComplete="off" value={key}
      onChange={event => { setKey(event.target.value); setSaved(false); }}
      className="w-full rounded-lg border border-[var(--c-700)] bg-[var(--c-900)] p-3" />
    <div className="flex gap-3">
      <button type="submit" className="rounded-lg bg-[var(--c-200)] text-[var(--c-950)] px-4 py-2">保存密钥</button>
      <button type="button" onClick={() => save('')} className="rounded-lg border border-[var(--c-700)] px-4 py-2">清除密钥</button>
    </div>
    {saved && <p role="status" className="text-sm text-emerald-400">已更新，页面请求将使用当前配置。</p>}
  </form>;
}
