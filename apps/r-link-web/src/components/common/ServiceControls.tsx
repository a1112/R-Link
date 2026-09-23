import { useRef, useState, type InputHTMLAttributes, type ReactNode } from 'react';

export const serviceButton = 'rounded-lg border border-[var(--c-700)] px-3 py-2 text-sm disabled:opacity-40';
export const serviceInput = 'block w-full mt-1 rounded border border-[var(--c-700)] bg-[var(--c-900)] px-3 py-2 text-sm';
export function ServiceField({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label className="text-sm">{label}<input className={serviceInput} {...props} /></label>;
}
export function ServiceMessage({ error, children }: { error?: string | null; children?: ReactNode }) {
  return <>{error && <p role="alert" className="text-red-400 break-words">{error}</p>}{children}</>;
}
export function ServiceLogs({ value, close }: { value: string | null; close: () => void }) {
  if (value === null) return null;
  return <div className="rounded-xl border border-[var(--c-700)] p-4"><button className={serviceButton} onClick={close}>关闭日志</button><pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-all text-xs">{value || '暂无日志'}</pre></div>;
}
export function useServiceAction() {
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState('');
  const run = async (action: () => Promise<unknown>) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError('');
    try { await action(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { pending.current = false; setBusy(false); }
  };
  return { busy, error, run };
}
