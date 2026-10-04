import { listen } from '@tauri-apps/api/event';
import { isTauriRuntime } from './utils/tauriWindow';
import type { Device } from './api/devices';
import type { DeviceInitialAction } from './components/pages/RemoteView';
import React, { useCallback, useEffect, useState } from "react";
import { Toaster } from "sonner";
import { getThemeStyles, type ThemeName } from "./constants/theme";
import type { RouteId } from "./constants/routes";
import { MainLayout } from "./components/layout";
import { TopologyView } from "./components/TopologyView";
import { DashboardView } from "./components/DashboardView";
import { PluginsView } from "./components/PluginsView";
import { NetworkMonitor } from './components/NetworkMonitor';

const RemoteView = React.lazy(() => import('./components/pages/RemoteView'));
const FRPView = React.lazy(() => import('./components/pages/FRPView'));
const MeshView = React.lazy(() => import('./components/pages/MeshView'));
const DomainView = React.lazy(() => import('./components/pages/DomainView'));
const StorageView = React.lazy(() => import('./components/pages/StorageView'));
const RFileView = React.lazy(() => import('./components/pages/RFileView'));
const SSHView = React.lazy(() => import('./components/pages/SSHView'));
const ConsoleView = React.lazy(() => import('./components/pages/ConsoleView'));
const DownloadsView = React.lazy(() => import('./components/pages/DownloadsView'));

export default function App() {
  const [activeTab, setActiveTab] = useState<RouteId>('network');
  const [deviceAction, setDeviceAction] = useState<DeviceInitialAction | null>(null);
  const clearDeviceAction = useCallback(() => setDeviceAction(null), []);
  const navigate = (route: RouteId) => { setDeviceAction(null); setActiveTab(route); };
  const [sshVisited, setSshVisited] = useState(false);
  useEffect(() => { if (activeTab === 'ssh') setSshVisited(true); }, [activeTab]);
  const [sshTarget, setSshTarget] = useState<Device | null>(null);
  const [theme, setTheme] = useState<ThemeName>('zinc');
  const [accessRevision, setAccessRevision] = useState(0);
  useEffect(() => {
    const refresh = () => {
      setSshTarget(null);
      setDeviceAction(null);
      setSshVisited(false);
      setAccessRevision(value => value + 1);
    };
    window.addEventListener('r-link-service-access-changed', refresh);
    return () => window.removeEventListener('r-link-service-access-changed', refresh);
  }, []);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    let active = true;
    const unlisten = listen<string>('desktop-action', event => {
      if (!active) return;
      setDeviceAction(null);
      if (event.payload !== 'settings') window.dispatchEvent(new Event('r-link-close-settings'));
      if (event.payload === 'devices') setActiveTab('remote');
      if (event.payload === 'dashboard') setActiveTab('dashboard');
      if (event.payload === 'network') setActiveTab('network');
      if (event.payload === 'plugins') setActiveTab('plugins');
      if (event.payload === 'storage') setActiveTab('storage');
      if (event.payload === 'ssh') setActiveTab('ssh');
      if (event.payload === 'settings') window.dispatchEvent(new Event('r-link-open-settings'));
    });
    return () => { active = false; void unlisten.then(stop => stop()).catch(() => undefined); };
  }, []);

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard': return <DashboardView />;
      case 'analytics': return <NetworkMonitor />;
      case 'network': return <TopologyView onManage={device => { setDeviceAction(device ? { kind: 'edit', deviceId: device.id } : { kind: 'add' }); setActiveTab('remote'); }} onSsh={device => { setSshTarget(device); setActiveTab('ssh'); }} onRFile={() => setActiveTab('rfile')} onStorage={() => setActiveTab('storage')} />;
      case 'mesh': return <MeshView />;
      case 'plugins': return <PluginsView />;
      case 'remote': return <RemoteView initialAction={deviceAction} onInitialActionHandled={clearDeviceAction} onSsh={device => { setSshTarget(device); setActiveTab('ssh'); }} />;
      case 'frp': return <FRPView />;
      case 'domains': return <DomainView />;
      case 'storage': return <StorageView />;
      case 'rfile': return <RFileView />;
      case 'ssh': return null;
      case 'console': return <ConsoleView />;
      case 'downloads': return <DownloadsView />;
      default: return <div className="text-[var(--c-500)]">开发中...</div>;
    }
  };

  return (
    <div className="flex h-screen bg-[var(--c-950)] text-[var(--c-200)] font-sans overflow-hidden" style={getThemeStyles(theme)}>
      <Toaster position="bottom-right" theme="dark" />
      <MainLayout activeRoute={activeTab} onRouteChange={navigate} currentTheme={theme} onThemeChange={setTheme}>
        <React.Suspense key={accessRevision} fallback={<div className="p-6">加载中...</div>}>
          <div className={activeTab === 'ssh' ? 'h-full' : 'hidden'}>
            {(sshVisited || activeTab === 'ssh') && <SSHView initialTarget={sshTarget} />}
          </div>
          {activeTab !== 'ssh' && renderContent()}
        </React.Suspense>
      </MainLayout>
    </div>
  );
}
