import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { TitleBar } from './TitleBar';
import { isTauriRuntime } from '../../utils/tauriWindow';
import { SettingsModal, TermsModal } from '../modals';
import { getRouteById, type RouteId, type ThemeName } from '@/constants';
import { AccountControl, type AccountActions } from '../AccountPanel';
import { isAccountAdmin } from '../../api/account-access';

export interface MainLayoutProps {
  activeRoute: RouteId;
  onRouteChange: (route: RouteId) => void;
  currentTheme?: ThemeName;
  onThemeChange?: (theme: ThemeName) => void;
  children: React.ReactNode;
  allowedRoutes?: RouteId[];
  accountActions?: AccountActions;
}

export function MainLayout({ activeRoute, onRouteChange, currentTheme = 'zinc', onThemeChange, children, allowedRoutes, accountActions }: MainLayoutProps) {
  const [collapsed, setCollapsed] = useState(() => window.matchMedia?.('(max-width: 767px)').matches ?? false);
  const [showSettings, setShowSettings] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  useEffect(() => {
    const narrow = window.matchMedia?.('(max-width: 767px)');
    if (!narrow) return;
    const resize = (event: MediaQueryListEvent) => { if (event.matches) setCollapsed(true); };
    narrow.addEventListener('change', resize);
    return () => narrow.removeEventListener('change', resize);
  }, []);
  useEffect(() => {
    const open = () => setShowSettings(true);
    const close = () => setShowSettings(false);
    window.addEventListener('r-link-open-settings', open);
    window.addEventListener('r-link-close-settings', close);
    return () => {
      window.removeEventListener('r-link-open-settings', open);
      window.removeEventListener('r-link-close-settings', close);
    };
  }, []);
  return <div className="flex w-full h-full">
    <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} activeRoute={activeRoute} onRouteChange={onRouteChange} allowedRoutes={allowedRoutes} />
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[var(--c-950)] relative">
      {isTauriRuntime() && <TitleBar showMenu={false} />}
      <Header title={getRouteById(activeRoute)?.title || 'R-Link'} onOpenSettings={() => setShowSettings(true)} onOpenTerms={() => setShowTerms(true)} accountControl={accountActions && <AccountControl actions={accountActions} />} />
      <div className={`flex-1 min-h-0 overflow-y-auto relative ${activeRoute === 'network' ? 'p-3 lg:p-5' : 'p-3 md:p-6'}`}>
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.15 }} className="h-full">
            {children}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
    <SettingsModal show={showSettings} onClose={() => setShowSettings(false)} currentTheme={currentTheme} onThemeChange={theme => onThemeChange?.(theme)} accountMode={accountActions?.account.config?.mode === 'oidc'} canManageUsers={accountActions ? !!isAccountAdmin(accountActions.account) : false} identityRevision={accountActions?.account.revision} />
    <TermsModal show={showTerms} onClose={() => setShowTerms(false)} onAgree={() => setShowTerms(false)} forceAgree={false} />
  </div>;
}

export default MainLayout;
