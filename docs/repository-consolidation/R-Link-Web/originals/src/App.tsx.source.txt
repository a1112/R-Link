/**
 * R-Link 主应用组件（重构版）
 */

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Toaster } from "sonner@2.0.3";

// 常量
import { getThemeStyles, type ThemeName } from "./constants/theme";
import { routes, type RouteId } from "./constants/routes";

// 布局组件
import { MainLayout } from "./components/layout";

// 页面组件
import { AuthScreen } from "./components/pages";
import { TopologyView } from "./components/TopologyView";
import { DashboardView as ApiDashboardView } from "./components/DashboardView";
import { PluginsView as ApiPluginsView } from "./components/PluginsView";

// 弹窗组件
import { TermsModal } from "./components/modals/TermsModal";

// 类型定义
type AppState = 'auth' | 'app' | 'guest';

/**
 * R-Link 主应用
 */
const App: React.FC = () => {
  const [route, setRoute] = useState<AppState>('app');
  const [activeTab, setActiveTab] = useState<RouteId>("dashboard");
  const [theme, setTheme] = useState<ThemeName>("zinc");

  // 用户协议弹窗状态
  const [showTermsModal, setShowTermsModal] = useState(false);

  // 检查是否已同意过协议
  const hasAgreedToTerms = useMemo(() => {
    return localStorage.getItem('r-link-terms-agreed') === 'true';
  }, []);

  const themeStyles = useMemo(() => getThemeStyles(theme), [theme]);

  // 状态计算
  const isGuest = route === 'guest';
  const isAuthenticated = route !== 'auth';

  // 处理登录
  const handleLogin = () => {
    setRoute('app');
    // 如果还没同意过协议，显示协议弹窗
    if (!hasAgreedToTerms) {
      setShowTermsModal(true);
    }
  };

  // 处理游客登录
  const handleGuestLogin = () => {
    setRoute('guest');
    // 游客也需要同意协议
    if (!hasAgreedToTerms) {
      setShowTermsModal(true);
    }
  };

  // 处理同意协议
  const handleAgreeToTerms = () => {
    localStorage.setItem('r-link-terms-agreed', 'true');
    setShowTermsModal(false);
  };

  // 处理拒绝协议（关闭弹窗但不记录同意）
  const handleCloseTerms = () => {
    setShowTermsModal(false);
    // 可选：退出登录状态
    // setRoute('auth');
  };

  // 处理登出
  const handleLogout = () => {
    setRoute('auth');
    setActiveTab("dashboard");
  };

  // 处理路由变更
  const handleRouteChange = (newRoute: RouteId) => {
    setActiveTab(newRoute);
  };

  // 渲染内容
  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <ApiDashboardView />;
      case 'network':
        return <TopologyView />;
      case 'plugins':
        return <ApiPluginsView />;
      case 'remote':
        // 使用懒加载
        return React.createElement(
          React.lazy(() => import('./components/pages/RemoteView')),
          null
        );
      case 'frp':
        return React.createElement(
          React.lazy(() => import('./components/pages/FRPView')),
          null
        );
      case 'domains':
        return React.createElement(
          React.lazy(() => import('./components/pages/DomainView')),
          null
        );
      case 'storage':
        return React.createElement(
          React.lazy(() => import('./components/pages/StorageView')),
          null
        );
      case 'ssh':
        return React.createElement(
          React.lazy(() => import('./components/pages/SSHView')),
          null
        );
      case 'console':
        return React.createElement(
          React.lazy(() => import('./components/pages/ConsoleView')),
          null
        );
      case 'downloads':
        return React.createElement(
          React.lazy(() => import('./components/pages/DownloadsView')),
          null
        );
      case 'profile':
        return React.createElement(
          React.lazy(() => import('./components/pages/ProfileView')),
          null
        );
      default:
        return <div className="text-[var(--c-500)]">开发中...</div>;
    }
  };

  return (
    <div
      className="flex h-screen bg-[var(--c-950)] text-[var(--c-200)] font-sans selection:bg-[var(--c-800)] selection:text-[var(--c-white)] overflow-hidden"
      style={themeStyles}
    >
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          style: {
            background: 'var(--c-900)',
            border: '1px solid var(--c-800)',
            color: 'var(--c-100)'
          }
        }}
      />

      <AnimatePresence mode="wait">
        {!isAuthenticated ? (
          <motion.div
            key="auth"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.05, filter: "blur(10px)" }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-50"
          >
            <AuthScreen
              onLogin={handleLogin}
              onGuestLogin={handleGuestLogin}
            />
          </motion.div>
        ) : (
          <motion.div
            key="app-shell"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            className="flex w-full h-full"
          >
            <React.Suspense fallback={<div className="flex-1 flex items-center justify-center text-[var(--c-500)]">加载中...</div>}>
              <MainLayout
                activeRoute={activeTab}
                onRouteChange={handleRouteChange}
                isGuest={isGuest}
                currentTheme={theme}
                onThemeChange={setTheme}
                onLogout={handleLogout}
              >
                {renderContent()}
              </MainLayout>
            </React.Suspense>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 用户协议弹窗 */}
      <TermsModal
        show={showTermsModal}
        onClose={handleCloseTerms}
        onAgree={handleAgreeToTerms}
        forceAgree={false}
        title="使用条款与隐私政策"
      />
    </div>
  );
};

export default App;
