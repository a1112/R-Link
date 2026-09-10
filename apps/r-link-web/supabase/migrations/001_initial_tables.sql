-- ============================================
-- R-Link Supabase 数据库表结构
-- 在 Supabase Dashboard -> SQL Editor 中执行此脚本
-- ============================================

-- ============================================
-- 1. 用户扩展表 (profiles)
-- 扩展 auth.users 表的额外信息
-- ============================================

CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  email TEXT NOT NULL,
  username TEXT UNIQUE,
  full_name TEXT,
  avatar_url TEXT,
  bio TEXT,
  role TEXT DEFAULT 'user' CHECK (role IN ('admin', 'user', 'guest')),
  preferences JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 添加注释
COMMENT ON TABLE public.profiles IS '用户扩展信息表';
COMMENT ON COLUMN public.profiles.id IS '用户 ID，关联 auth.users';
COMMENT ON COLUMN public.profiles.email IS '邮箱';
COMMENT ON COLUMN public.profiles.username IS '用户名（唯一）';
COMMENT ON COLUMN public.profiles.full_name IS '全名';
COMMENT ON COLUMN public.profiles.avatar_url IS '头像 URL';
COMMENT ON COLUMN public.profiles.bio IS '个人简介';
COMMENT ON COLUMN public.profiles.role IS '用户角色：admin/admin/user/guest';
COMMENT ON COLUMN public.profiles.preferences IS '用户偏好设置（JSON）';

-- ============================================
-- 2. 插件配置表 (plugin_configs)
-- 存储用户的插件配置
-- ============================================

CREATE TABLE IF NOT EXISTS public.plugin_configs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  plugin_id TEXT NOT NULL,
  plugin_name TEXT,
  config JSONB DEFAULT '{}'::jsonb,
  enabled BOOLEAN DEFAULT true,
  auto_start BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  UNIQUE(user_id, plugin_id)
);

COMMENT ON TABLE public.plugin_configs IS '用户插件配置表';
COMMENT ON COLUMN public.plugin_configs.plugin_id IS '插件 ID';
COMMENT ON COLUMN public.plugin_configs.config IS '插件配置（JSON）';
COMMENT ON COLUMN public.plugin_configs.enabled IS '是否启用';
COMMENT ON COLUMN public.plugin_configs.auto_start IS '是否自动启动';

-- ============================================
-- 3. 插件市场表 (plugin_market)
-- 插件市场信息
-- ============================================

CREATE TABLE IF NOT EXISTS public.plugin_market (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  plugin_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  version TEXT DEFAULT '1.0.0',
  author TEXT,
  category TEXT,
  icon_url TEXT,
  homepage_url TEXT,
  repository_url TEXT,
  download_url TEXT,
  file_size BIGINT,
  min_app_version TEXT,
  tags TEXT[] DEFAULT '{}',
  screenshots TEXT[] DEFAULT '{}',
  downloads INTEGER DEFAULT 0,
  rating DECIMAL(3,2) DEFAULT 0,
  rating_count INTEGER DEFAULT 0,
  is_builtin BOOLEAN DEFAULT false,
  is_official BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'deprecated', 'removed')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.plugin_market IS '插件市场表';
COMMENT ON COLUMN public.plugin_market.plugin_id IS '插件唯一标识';
COMMENT ON COLUMN public.plugin_market.rating IS '评分 (0.00-5.00)';
COMMENT ON COLUMN public.plugin_market.is_builtin IS '是否为内置插件';

-- ============================================
-- 4. 插件评论表 (plugin_reviews)
-- 插件评论和评分
-- ============================================

CREATE TABLE IF NOT EXISTS public.plugin_reviews (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  plugin_id TEXT NOT NULL REFERENCES public.plugin_market(plugin_id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  rating INTEGER CHECK (rating >= 1 AND rating <= 5),
  title TEXT,
  content TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  UNIQUE(plugin_id, user_id)
);

COMMENT ON TABLE public.plugin_reviews IS '插件评论表';

-- ============================================
-- 5. 用户设置表 (user_settings)
-- 用户应用设置
-- ============================================

CREATE TABLE IF NOT EXISTS public.user_settings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE UNIQUE NOT NULL,
  theme TEXT DEFAULT 'dark' CHECK (theme IN ('dark', 'light', 'auto')),
  language TEXT DEFAULT 'zh-CN',
  timezone TEXT DEFAULT 'Asia/Shanghai',
  notifications_enabled BOOLEAN DEFAULT true,
  email_notifications BOOLEAN DEFAULT true,
  desktop_notifications BOOLEAN DEFAULT false,
  auto_start_plugins TEXT[] DEFAULT '{}',
  dashboard_layout JSONB DEFAULT '{}'::jsonb,
  sidebar_collapsed BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.user_settings IS '用户应用设置表';

-- ============================================
-- 6. 远程连接表 (remote_connections)
-- 远程服务器连接配置
-- ============================================

CREATE TABLE IF NOT EXISTS public.remote_connections (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  type TEXT DEFAULT 'ssh' CHECK (type IN ('ssh', 'rdp', 'vnc', 'sftp', 'ftp', 'custom')),
  host TEXT NOT NULL,
  port INTEGER,
  username TEXT,
  password_encrypted TEXT,
  private_key_encrypted TEXT,
  auth_method TEXT DEFAULT 'password' CHECK (auth_method IN ('password', 'key', 'both')),
  tags TEXT[] DEFAULT '{}',
  description TEXT,
  group_name TEXT,
  is_favorite BOOLEAN DEFAULT false,
  last_connected_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.remote_connections IS '远程连接配置表';
COMMENT ON COLUMN public.remote_connections.password_encrypted IS '加密后的密码';
COMMENT ON COLUMN public.remote_connections.private_key_encrypted IS '加密后的私钥';

-- ============================================
-- 7. 连接历史表 (connection_history)
-- 连接历史记录
-- ============================================

CREATE TABLE IF NOT EXISTS public.connection_history (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  connection_id UUID REFERENCES public.remote_connections(id) ON DELETE SET NULL,
  connection_name TEXT,
  status TEXT DEFAULT 'connected' CHECK (status IN ('connected', 'disconnected', 'failed')),
  error_message TEXT,
  duration_seconds INTEGER,
  connected_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  disconnected_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE public.connection_history IS '连接历史记录表';

-- ============================================
-- 8. FRP 配置表 (frp_configs)
-- FRP 内网穿透配置
-- ============================================

CREATE TABLE IF NOT EXISTS public.frp_configs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  server_addr TEXT NOT NULL,
  server_port INTEGER DEFAULT 7000,
  auth_token TEXT,
  proxies JSONB DEFAULT '[]'::jsonb,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.frp_configs IS 'FRP 内网穿透配置表';
COMMENT ON COLUMN public.frp_configs.proxies IS '代理配置列表（JSON 数组）';

-- ============================================
-- 9. 存储映射表 (storage_mappings)
-- 存储映射配置
-- ============================================

CREATE TABLE IF NOT EXISTS public.storage_mappings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  type TEXT DEFAULT 'local' CHECK (type IN ('local', 's3', 'webdav', 'onedrive', 'google')),
  config JSONB DEFAULT '{}'::jsonb,
  mount_point TEXT,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.storage_mappings IS '存储映射配置表';

-- ============================================
-- 10. 系统通知表 (notifications)
-- 系统通知
-- ============================================

CREATE TABLE IF NOT EXISTS public.notifications (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  type TEXT DEFAULT 'info' CHECK (type IN ('info', 'success', 'warning', 'error')),
  title TEXT NOT NULL,
  message TEXT,
  action_url TEXT,
  action_label TEXT,
  read BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
  expires_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE public.notifications IS '系统通知表';

-- ============================================
-- 11. API 密钥表 (api_keys)
-- API 密钥管理
-- ============================================

CREATE TABLE IF NOT EXISTS public.api_keys (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL UNIQUE,
  scopes TEXT[] DEFAULT '{"read"}',
  last_used_at TIMESTAMP WITH TIME ZONE,
  expires_at TIMESTAMP WITH TIME ZONE,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.api_keys IS 'API 密钥管理表';

-- ============================================
-- 12. 审计日志表 (audit_logs)
-- 操作审计日志
-- ============================================

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE SET NULL,
  action TEXT NOT NULL,
  resource_type TEXT,
  resource_id TEXT,
  details JSONB DEFAULT '{}'::jsonb,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 创建索引用于查询优化
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at DESC);

COMMENT ON TABLE public.audit_logs IS '操作审计日志表';

-- ============================================
-- 13. 系统配置表 (system_config)
-- 系统级配置（仅管理员）
-- ============================================

CREATE TABLE IF NOT EXISTS public.system_config (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  description TEXT,
  updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.system_config IS '系统级配置表';

-- 插入默认系统配置
INSERT INTO public.system_config (key, value, description) VALUES
  ('maintenance_mode', 'false', '维护模式'),
  ('registration_enabled', 'true', '是否允许注册'),
  ('max_connections_per_user', '100', '每个用户最大连接数')
ON CONFLICT (key) DO NOTHING;

-- ============================================
-- 14. 文件存储表 (files)
-- 文件上传记录
-- ============================================

CREATE TABLE IF NOT EXISTS public.files (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_size BIGINT,
  mime_type TEXT,
  storage_type TEXT DEFAULT 'supabase' CHECK (storage_type IN ('supabase', 's3', 'local')),
  bucket_name TEXT DEFAULT 'files',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

COMMENT ON TABLE public.files IS '文件上传记录表';

-- ============================================
-- 启用行级安全策略 (RLS)
-- ============================================

-- 启用 RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plugin_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plugin_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.remote_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.connection_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.frp_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.storage_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;

-- ============================================
-- RLS 策略：profiles
-- ============================================

-- 用户可以查看自己的资料
CREATE POLICY "Users can view own profile"
  ON public.profiles FOR SELECT
  USING (auth.uid() = id);

-- 用户可以更新自己的资料
CREATE POLICY "Users can update own profile"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id);

-- 所有人可以插入自己的资料（注册时）
CREATE POLICY "Users can insert own profile"
  ON public.profiles FOR INSERT
  WITH CHECK (auth.uid() = id);

-- ============================================
-- RLS 策略：plugin_configs
-- ============================================

CREATE POLICY "Users can view own plugin configs"
  ON public.plugin_configs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own plugin configs"
  ON public.plugin_configs FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：plugin_market
-- ============================================

-- 所有人可以查看插件市场
ALTER TABLE public.plugin_market ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Everyone can view plugin market"
  ON public.plugin_market FOR SELECT
  USING (true);

-- ============================================
-- RLS 策略：plugin_reviews
-- ============================================

CREATE POLICY "Everyone can view reviews"
  ON public.plugin_reviews FOR SELECT
  USING (true);

CREATE POLICY "Users can manage own reviews"
  ON public.plugin_reviews FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：user_settings
-- ============================================

CREATE POLICY "Users can manage own settings"
  ON public.user_settings FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：remote_connections
-- ============================================

CREATE POLICY "Users can manage own connections"
  ON public.remote_connections FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：connection_history
-- ============================================

CREATE POLICY "Users can view own connection history"
  ON public.connection_history FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own connection history"
  ON public.connection_history FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own connection history"
  ON public.connection_history FOR UPDATE
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：frp_configs
-- ============================================

CREATE POLICY "Users can manage own frp configs"
  ON public.frp_configs FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：storage_mappings
-- ============================================

CREATE POLICY "Users can manage own storage mappings"
  ON public.storage_mappings FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：notifications
-- ============================================

CREATE POLICY "Users can manage own notifications"
  ON public.notifications FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：api_keys
-- ============================================

CREATE POLICY "Users can manage own api keys"
  ON public.api_keys FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- RLS 策略：files
-- ============================================

CREATE POLICY "Users can manage own files"
  ON public.files FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- 创建索引
-- ============================================

-- profiles 索引
CREATE INDEX IF NOT EXISTS idx_profiles_username ON public.profiles(username);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);

-- plugin_configs 索引
CREATE INDEX IF NOT EXISTS idx_plugin_configs_user_id ON public.plugin_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_plugin_configs_plugin_id ON public.plugin_configs(plugin_id);
CREATE INDEX IF NOT EXISTS idx_plugin_configs_enabled ON public.plugin_configs(enabled);

-- plugin_market 索引
CREATE INDEX IF NOT EXISTS idx_plugin_market_category ON public.plugin_market(category);
CREATE INDEX IF NOT EXISTS idx_plugin_market_status ON public.plugin_market(status);
CREATE INDEX IF NOT EXISTS idx_plugin_market_downloads ON public.plugin_market(downloads DESC);

-- plugin_reviews 索引
CREATE INDEX IF NOT EXISTS idx_plugin_reviews_plugin_id ON public.plugin_reviews(plugin_id);
CREATE INDEX IF NOT EXISTS idx_plugin_reviews_user_id ON public.plugin_reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_plugin_reviews_rating ON public.plugin_reviews(rating);

-- remote_connections 索引
CREATE INDEX IF NOT EXISTS idx_remote_connections_user_id ON public.remote_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_remote_connections_type ON public.remote_connections(type);
CREATE INDEX IF NOT EXISTS idx_remote_connections_group ON public.remote_connections(group_name);

-- connection_history 索引
CREATE INDEX IF NOT EXISTS idx_connection_history_user_id ON public.connection_history(user_id);
CREATE INDEX IF NOT EXISTS idx_connection_history_connected_at ON public.connection_history(connected_at DESC);

-- notifications 索引
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON public.notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON public.notifications(read);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON public.notifications(created_at DESC);

-- ============================================
-- 自动更新 updated_at 的触发器函数
-- ============================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = TIMEZONE('utc', NOW());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要的表添加触发器
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_plugin_configs_updated_at BEFORE UPDATE ON public.plugin_configs
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_plugin_market_updated_at BEFORE UPDATE ON public.plugin_market
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_plugin_reviews_updated_at BEFORE UPDATE ON public.plugin_reviews
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON public.user_settings
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_remote_connections_updated_at BEFORE UPDATE ON public.remote_connections
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_frp_configs_updated_at BEFORE UPDATE ON public.frp_configs
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_storage_mappings_updated_at BEFORE UPDATE ON public.storage_mappings
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================
-- 创建新用户时自动创建 profile 的触发器
-- ============================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, username, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'username', SPLIT_PART(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'full_name', SPLIT_PART(NEW.email, '@', 1))
  );

  -- 创建默认用户设置
  INSERT INTO public.user_settings (user_id)
  VALUES (NEW.id);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- 启用实时订阅
-- ============================================

ALTER PUBLICATION supabase_realtime ADD TABLE public.plugin_configs;
ALTER PUBLICATION supabase_realtime ADD TABLE public.notifications;
ALTER PUBLICATION supabase_realtime ADD TABLE public.connection_history;

-- ============================================
-- 完成
-- ============================================

-- 创建视图用于统计
CREATE OR REPLACE VIEW public.user_stats AS
SELECT
  p.id as user_id,
  p.username,
  COUNT(DISTINCT pc.id) FILTER (WHERE pc.enabled) as active_plugins,
  COUNT(DISTINCT rc.id) as total_connections,
  COUNT(DISTINCT ch.id) FILTER (WHERE ch.created_at > NOW() - INTERVAL '30 days') as recent_connections,
  p.created_at as member_since
FROM public.profiles p
LEFT JOIN public.plugin_configs pc ON p.id = pc.user_id
LEFT JOIN public.remote_connections rc ON p.id = rc.user_id
LEFT JOIN public.connection_history ch ON p.id = ch.user_id
GROUP BY p.id, p.username, p.created_at;

COMMENT ON VIEW public.user_stats IS '用户统计视图';
