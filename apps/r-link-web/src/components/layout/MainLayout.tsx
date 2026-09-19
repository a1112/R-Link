import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { TitleBar } from './TitleBar';
import { isTauriRuntime } from '../../utils/tauriWindow';
import { SettingsModal, TermsModal } from '../modals';
import { getRouteById, type RouteId, type ThemeName } from '@/constants';

export interface MainLayoutProps {
  activeRoute: RouteId;
  onRouteChange: (route: RouteId) => void;
  currentTheme?: ThemeName;
  onThemeChange?: (theme: ThemeName) => void;
  children: React.ReactNode;
}

export function MainLayout({ activeRoute, onRouteChange, currentTheme = 'zinc', onThemeChange, children }: MainLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  useEffect(() => {
    const open = () => setShowSettings(true);
    window.addEventListener('r-link-open-settings', open);
    return () => window.removeEventListener('r-link-open-settings', open);
  }, []);
  return <div className="flex w-full h-full">
    <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} activeRoute={activeRoute} onRouteChange={onRouteChange} />
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[var(--c-950)] relative">
      {isTauriRuntime() && <TitleBar showMenu={false} />}
      <Header title={getRouteById(activeRoute)?.title || 'R-Link'} onOpenSettings={() => setShowSettings(true)} onOpenTerms={() => setShowTerms(true)} />
      <div className="flex-1 min-h-0 overflow-y-auto p-6 relative">
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.15 }} className="h-full">
            {children}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
    <SettingsModal show={showSettings} onClose={() => setShowSettings(false)} currentTheme={currentTheme} onThemeChange={theme => onThemeChange?.(theme)} />
    <TermsModal show={showTerms} onClose={() => setShowTerms(false)} onAgree={() => setShowTerms(false)} forceAgree={false} />
  </div>;
}

export default MainLayout;
