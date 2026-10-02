const addressKey = 'r-link-service-url';

function normalize(value: string): string {
  if (!value.trim()) return '';
  let url: URL;
  try { url = new URL(value.trim()); }
  catch { throw new Error('请输入完整的服务地址，例如 https://rlink.example.com'); }
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && local))
    || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('服务地址须为 HTTPS 源地址；HTTP 仅限本机。请勿包含账号、路径或查询参数。');
  }
  return url.origin;
}

/** Persist the public endpoint; access keys remain in per-origin session storage. */
export function getServiceUrl(): string {
  try { return normalize(localStorage.getItem(addressKey) || ''); }
  catch { return ''; }
}

export function setServiceUrl(value: string): void {
  const address = normalize(value);
  if (address) localStorage.setItem(addressKey, address);
  else localStorage.removeItem(addressKey);
}
