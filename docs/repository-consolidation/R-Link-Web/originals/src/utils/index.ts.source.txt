/**
 * 工具函数统一导出
 */

// Tauri 窗口工具
export {
  withTauriWindow,
  isTauriRuntime,
  isElectronRuntime,
  isDesktopRuntime,
  type TauriWindowLike,
} from './tauriWindow';

// Supabase 客户端
export { supabase, createAdminClient } from './supabase/client';

// Supabase 数据库操作
export {
  profileApi,
  pluginConfigApi,
  userSettingsApi,
  pluginMarketApi,
  pluginReviewApi,
  remoteConnectionApi,
  connectionHistoryApi,
  frpConfigApi,
  storageMappingApi,
  notificationApi,
  systemConfigApi,
  subscriptionApi,
} from './supabase/database';

// Supabase 认证
export {
  authApi,
  authStore,
  createAuthStore,
  type AuthState,
  type SignInCredentials,
  type SignUpCredentials,
} from './supabase/auth';

// Supabase 类型
export type { Database } from './supabase/types';
