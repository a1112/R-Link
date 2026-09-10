import React, { useEffect, useState } from 'react';
import { AuthPage } from './AuthPage';
import { supabase, supabaseConfigured } from '../utils/supabase/client';
import { getThemeStyles } from '../constants/theme';

/** Mount management views only after a real Supabase session is available. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<'loading' | 'anonymous' | 'authenticated'>('loading');
  useEffect(() => {
    if (!supabaseConfigured) return;
    let disposed = false;
    let authEventReceived = false;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      authEventReceived = true;
      if (!disposed) setStatus(session ? 'authenticated' : 'anonymous');
    });
    void supabase.auth.getSession().then(({ data, error }) => {
      if (!disposed && !authEventReceived) setStatus(!error && data.session ? 'authenticated' : 'anonymous');
    }).catch(() => {
      if (!disposed && !authEventReceived) setStatus('anonymous');
    });
    return () => { disposed = true; subscription.unsubscribe(); };
  }, []);

  return <div style={getThemeStyles('zinc')} className="min-h-screen bg-[var(--c-950)] text-[var(--c-200)]">
    {!supabaseConfigured ? <p role="status" className="p-8">尚未配置登录服务，请按 README 配置并重启客户端。</p>
      : status === 'loading' ? <p role="status" className="p-8">正在检查登录状态…</p>
      : status === 'anonymous' ? <AuthPage onLogin={() => { /* Session event controls access. */ }} />
      : children}
  </div>;
}
