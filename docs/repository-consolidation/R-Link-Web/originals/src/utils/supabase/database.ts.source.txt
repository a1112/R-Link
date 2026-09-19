/**
 * Supabase 数据库操作封装
 * 提供类型安全的数据库 CRUD 操作
 */

import { supabase } from "./client";
import type { Database } from "./types";

type Tables = Database["public"]["Tables"];

// ============================================================
// 用户资料操作 (profiles)
// ============================================================

type Profiles = Tables["profiles"];

export const profileApi = {
  async getById(userId: string) {
    const { data, error } = await supabase
      .from("profiles")
      .select("*")
      .eq("id", userId)
      .single();

    if (error) throw error;
    return data as Profiles["Row"] | null;
  },

  async getByUsername(username: string) {
    const { data, error } = await supabase
      .from("profiles")
      .select("*")
      .eq("username", username)
      .single();

    if (error) throw error;
    return data as Profiles["Row"] | null;
  },

  async update(userId: string, updates: Partial<Omit<Profiles["Update"], "id">>) {
    const { data, error } = await supabase
      .from("profiles")
      .update({
        ...updates,
        updated_at: new Date().toISOString(),
      })
      .eq("id", userId)
      .select()
      .single();

    if (error) throw error;
    return data as Profiles["Row"];
  },

  async create(profile: Profiles["Insert"]) {
    const { data, error } = await supabase
      .from("profiles")
      .insert(profile)
      .select()
      .single();

    if (error) throw error;
    return data as Profiles["Row"];
  },
};

// ============================================================
// 插件配置操作 (plugin_configs)
// ============================================================

type PluginConfigs = Tables["plugin_configs"];

export const pluginConfigApi = {
  async getUserConfigs(userId: string) {
    const { data, error } = await supabase
      .from("plugin_configs")
      .select("*")
      .eq("user_id", userId);

    if (error) throw error;
    return data as PluginConfigs["Row"][];
  },

  async getPluginConfig(userId: string, pluginId: string) {
    const { data, error } = await supabase
      .from("plugin_configs")
      .select("*")
      .eq("user_id", userId)
      .eq("plugin_id", pluginId)
      .single();

    if (error) throw error;
    return data as PluginConfigs["Row"] | null;
  },

  async upsert(userId: string, pluginId: string, config: Record<string, any>, enabled = true) {
    const { data, error } = await supabase
      .from("plugin_configs")
      .upsert({
        user_id: userId,
        plugin_id: pluginId,
        config,
        enabled,
        updated_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (error) throw error;
    return data as PluginConfigs["Row"];
  },

  async delete(userId: string, pluginId: string) {
    const { error } = await supabase
      .from("plugin_configs")
      .delete()
      .eq("user_id", userId)
      .eq("plugin_id", pluginId);

    if (error) throw error;
  },

  async setEnabled(userId: string, pluginId: string, enabled: boolean) {
    const { data, error } = await supabase
      .from("plugin_configs")
      .update({ enabled, updated_at: new Date().toISOString() })
      .eq("user_id", userId)
      .eq("plugin_id", pluginId)
      .select()
      .single();

    if (error) throw error;
    return data as PluginConfigs["Row"];
  },

  async setAutoStart(userId: string, pluginId: string, autoStart: boolean) {
    const { data, error } = await supabase
      .from("plugin_configs")
      .update({ auto_start: autoStart, updated_at: new Date().toISOString() })
      .eq("user_id", userId)
      .eq("plugin_id", pluginId)
      .select()
      .single();

    if (error) throw error;
    return data as PluginConfigs["Row"];
  },
};

// ============================================================
// 插件市场操作 (plugin_market)
// ============================================================

type PluginMarket = Tables["plugin_market"];

export const pluginMarketApi = {
  async getAll(filters?: {
    category?: string;
    is_builtin?: boolean;
    is_official?: boolean;
    status?: "active" | "deprecated" | "removed";
  }) {
    let query = supabase
      .from("plugin_market")
      .select("*")
      .eq("status", "active");

    if (filters?.category) query = query.eq("category", filters.category);
    if (filters?.is_builtin !== undefined) query = query.eq("is_builtin", filters.is_builtin);
    if (filters?.is_official !== undefined) query = query.eq("is_official", filters.is_official);

    const { data, error } = await query;
    if (error) throw error;
    return data as PluginMarket["Row"][];
  },

  async getById(pluginId: string) {
    const { data, error } = await supabase
      .from("plugin_market")
      .select("*")
      .eq("plugin_id", pluginId)
      .single();

    if (error) throw error;
    return data as PluginMarket["Row"] | null;
  },

  async search(query: string) {
    const { data, error } = await supabase
      .from("plugin_market")
      .select("*")
      .or(`name.ilike.%${query}%,description.ilike.%${query}%,tags.cs.{${query}}`)
      .eq("status", "active");

    if (error) throw error;
    return data as PluginMarket["Row"][];
  },

  async incrementDownloads(pluginId: string) {
    const { data, error } = await supabase.rpc("increment_plugin_downloads", {
      p_plugin_id: pluginId,
    });

    if (error) throw error;
    return data;
  },
};

// ============================================================
// 插件评论操作 (plugin_reviews)
// ============================================================

type PluginReviews = Tables["plugin_reviews"];

export const pluginReviewApi = {
  async getPluginReviews(pluginId: string) {
    const { data, error } = await supabase
      .from("plugin_reviews")
      .select("*, profiles(id, username, avatar_url)")
      .eq("plugin_id", pluginId);

    if (error) throw error;
    return data;
  },

  async getUserReview(pluginId: string, userId: string) {
    const { data, error } = await supabase
      .from("plugin_reviews")
      .select("*")
      .eq("plugin_id", pluginId)
      .eq("user_id", userId)
      .single();

    if (error) throw error;
    return data as PluginReviews["Row"] | null;
  },

  async create(review: PluginReviews["Insert"]) {
    const { data, error } = await supabase
      .from("plugin_reviews")
      .insert(review)
      .select()
      .single();

    if (error) throw error;
    return data as PluginReviews["Row"];
  },

  async update(pluginId: string, userId: string, updates: Partial<PluginReviews["Update"]>) {
    const { data, error } = await supabase
      .from("plugin_reviews")
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq("plugin_id", pluginId)
      .eq("user_id", userId)
      .select()
      .single();

    if (error) throw error;
    return data as PluginReviews["Row"];
  },

  async delete(pluginId: string, userId: string) {
    const { error } = await supabase
      .from("plugin_reviews")
      .delete()
      .eq("plugin_id", pluginId)
      .eq("user_id", userId);

    if (error) throw error;
  },
};

// ============================================================
// 用户设置操作 (user_settings)
// ============================================================

type UserSettings = Tables["user_settings"];

export const userSettingsApi = {
  async get(userId: string) {
    const { data, error } = await supabase
      .from("user_settings")
      .select("*")
      .eq("user_id", userId)
      .single();

    if (error && error.code !== "PGRST116") throw error;
    return data as UserSettings["Row"] | null;
  },

  async update(userId: string, updates: Partial<Omit<UserSettings["Update"], "id" | "user_id">>) {
    const { data, error } = await supabase
      .from("user_settings")
      .update({
        ...updates,
        updated_at: new Date().toISOString(),
      })
      .eq("user_id", userId)
      .select()
      .single();

    if (error) {
      // 如果记录不存在，创建新记录
      if (error.code === "PGRST116") {
        return this.create(userId, updates);
      }
      throw error;
    }
    return data as UserSettings["Row"];
  },

  async create(userId: string, settings: Partial<Omit<UserSettings["Insert"], "id" | "user_id">>) {
    const { data, error } = await supabase
      .from("user_settings")
      .insert({
        user_id: userId,
        ...settings,
      })
      .select()
      .single();

    if (error) throw error;
    return data as UserSettings["Row"];
  },
};

// ============================================================
// 远程连接操作 (remote_connections)
// ============================================================

type RemoteConnections = Tables["remote_connections"];

export const remoteConnectionApi = {
  async getUserConnections(userId: string) {
    const { data, error } = await supabase
      .from("remote_connections")
      .select("*")
      .eq("user_id", userId)
      .order("created_at", { ascending: false });

    if (error) throw error;
    return data as RemoteConnections["Row"][];
  },

  async getById(connectionId: string, userId: string) {
    const { data, error } = await supabase
      .from("remote_connections")
      .select("*")
      .eq("id", connectionId)
      .eq("user_id", userId)
      .single();

    if (error) throw error;
    return data as RemoteConnections["Row"] | null;
  },

  async create(connection: RemoteConnections["Insert"]) {
    const { data, error } = await supabase
      .from("remote_connections")
      .insert(connection)
      .select()
      .single();

    if (error) throw error;
    return data as RemoteConnections["Row"];
  },

  async update(connectionId: string, userId: string, updates: Partial<RemoteConnections["Update"]>) {
    const { data, error } = await supabase
      .from("remote_connections")
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq("id", connectionId)
      .eq("user_id", userId)
      .select()
      .single();

    if (error) throw error;
    return data as RemoteConnections["Row"];
  },

  async delete(connectionId: string, userId: string) {
    const { error } = await supabase
      .from("remote_connections")
      .delete()
      .eq("id", connectionId)
      .eq("user_id", userId);

    if (error) throw error;
  },

  async updateLastConnected(connectionId: string) {
    const { error } = await supabase
      .from("remote_connections")
      .update({ last_connected_at: new Date().toISOString() })
      .eq("id", connectionId);

    if (error) throw error;
  },
};

// ============================================================
// 连接历史操作 (connection_history)
// ============================================================

type ConnectionHistory = Tables["connection_history"];

export const connectionHistoryApi = {
  async getUserHistory(userId: string, limit = 50) {
    const { data, error } = await supabase
      .from("connection_history")
      .select("*")
      .eq("user_id", userId)
      .order("connected_at", { ascending: false })
      .limit(limit);

    if (error) throw error;
    return data as ConnectionHistory["Row"][];
  },

  async getConnectionHistory(connectionId: string, limit = 20) {
    const { data, error } = await supabase
      .from("connection_history")
      .select("*")
      .eq("connection_id", connectionId)
      .order("connected_at", { ascending: false })
      .limit(limit);

    if (error) throw error;
    return data as ConnectionHistory["Row"][];
  },

  async create(record: ConnectionHistory["Insert"]) {
    const { data, error } = await supabase
      .from("connection_history")
      .insert(record)
      .select()
      .single();

    if (error) throw error;
    return data as ConnectionHistory["Row"];
  },

  async update(historyId: string, updates: Partial<ConnectionHistory["Update"]>) {
    const { data, error } = await supabase
      .from("connection_history")
      .update(updates)
      .eq("id", historyId)
      .select()
      .single();

    if (error) throw error;
    return data as ConnectionHistory["Row"];
  },
};

// ============================================================
// FRP 配置操作 (frp_configs)
// ============================================================

type FrpConfigs = Tables["frp_configs"];

export const frpConfigApi = {
  async getUserConfigs(userId: string) {
    const { data, error } = await supabase
      .from("frp_configs")
      .select("*")
      .eq("user_id", userId);

    if (error) throw error;
    return data as FrpConfigs["Row"][];
  },

  async create(config: FrpConfigs["Insert"]) {
    const { data, error } = await supabase
      .from("frp_configs")
      .insert(config)
      .select()
      .single();

    if (error) throw error;
    return data as FrpConfigs["Row"];
  },

  async update(configId: string, userId: string, updates: Partial<FrpConfigs["Update"]>) {
    const { data, error } = await supabase
      .from("frp_configs")
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq("id", configId)
      .eq("user_id", userId)
      .select()
      .single();

    if (error) throw error;
    return data as FrpConfigs["Row"];
  },

  async delete(configId: string, userId: string) {
    const { error } = await supabase
      .from("frp_configs")
      .delete()
      .eq("id", configId)
      .eq("user_id", userId);

    if (error) throw error;
  },
};

// ============================================================
// 存储映射操作 (storage_mappings)
// ============================================================

type StorageMappings = Tables["storage_mappings"];

export const storageMappingApi = {
  async getUserMappings(userId: string) {
    const { data, error } = await supabase
      .from("storage_mappings")
      .select("*")
      .eq("user_id", userId);

    if (error) throw error;
    return data as StorageMappings["Row"][];
  },

  async create(mapping: StorageMappings["Insert"]) {
    const { data, error } = await supabase
      .from("storage_mappings")
      .insert(mapping)
      .select()
      .single();

    if (error) throw error;
    return data as StorageMappings["Row"];
  },

  async update(mappingId: string, userId: string, updates: Partial<StorageMappings["Update"]>) {
    const { data, error } = await supabase
      .from("storage_mappings")
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq("id", mappingId)
      .eq("user_id", userId)
      .select()
      .single();

    if (error) throw error;
    return data as StorageMappings["Row"];
  },

  async delete(mappingId: string, userId: string) {
    const { error } = await supabase
      .from("storage_mappings")
      .delete()
      .eq("id", mappingId)
      .eq("user_id", userId);

    if (error) throw error;
  },
};

// ============================================================
// 通知操作 (notifications)
// ============================================================

type Notifications = Tables["notifications"];

export const notificationApi = {
  async getUserNotifications(userId: string, unreadOnly = false, limit = 50) {
    let query = supabase
      .from("notifications")
      .select("*")
      .eq("user_id", userId)
      .order("created_at", { ascending: false })
      .limit(limit);

    if (unreadOnly) {
      query = query.eq("read", false);
    }

    const { data, error } = await query;
    if (error) throw error;
    return data as Notifications["Row"][];
  },

  async getUnreadCount(userId: string) {
    const { data, error, count } = await supabase
      .from("notifications")
      .select("*", { count: "exact", head: true })
      .eq("user_id", userId)
      .eq("read", false);

    if (error) throw error;
    return count || 0;
  },

  async create(notification: Notifications["Insert"]) {
    const { data, error } = await supabase
      .from("notifications")
      .insert(notification)
      .select()
      .single();

    if (error) throw error;
    return data as Notifications["Row"];
  },

  async markAsRead(notificationId: string, userId: string) {
    const { data, error } = await supabase
      .from("notifications")
      .update({ read: true })
      .eq("id", notificationId)
      .eq("user_id", userId)
      .select()
      .single();

    if (error) throw error;
    return data as Notifications["Row"];
  },

  async markAllAsRead(userId: string) {
    const { error } = await supabase
      .from("notifications")
      .update({ read: true })
      .eq("user_id", userId)
      .eq("read", false);

    if (error) throw error;
  },

  async delete(notificationId: string, userId: string) {
    const { error } = await supabase
      .from("notifications")
      .delete()
      .eq("id", notificationId)
      .eq("user_id", userId);

    if (error) throw error;
  },
};

// ============================================================
// 系统配置操作 (system_config)
// ============================================================

type SystemConfig = Tables["system_config"];

export const systemConfigApi = {
  async get(key: string) {
    const { data, error } = await supabase
      .from("system_config")
      .select("*")
      .eq("key", key)
      .single();

    if (error) throw error;
    return data as SystemConfig["Row"] | null;
  },

  async getMany(keys: string[]) {
    const { data, error } = await supabase
      .from("system_config")
      .select("*")
      .in("key", keys);

    if (error) throw error;
    return data as SystemConfig["Row"][];
  },

  async getAll() {
    const { data, error } = await supabase
      .from("system_config")
      .select("*");

    if (error) throw error;
    return data as SystemConfig["Row"][];
  },

  async set(key: string, value: any, description?: string, updatedBy?: string) {
    const { data, error } = await supabase
      .from("system_config")
      .upsert({
        key,
        value,
        description,
        updated_by: updatedBy,
        updated_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (error) throw error;
    return data as SystemConfig["Row"];
  },
};

// ============================================================
// 实时订阅
// ============================================================

export const subscriptionApi = {
  subscribeToPluginConfigs(
    userId: string,
    callback: (payload: {
      eventType: "INSERT" | "UPDATE" | "DELETE";
      record: PluginConfigs["Row"];
    }) => void
  ) {
    return supabase
      .channel(`plugin_configs:${userId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "plugin_configs",
          filter: `user_id=eq.${userId}`,
        },
        callback
      )
      .subscribe();
  },

  subscribeToNotifications(
    userId: string,
    callback: (payload: {
      eventType: "INSERT" | "UPDATE" | "DELETE";
      record: Notifications["Row"];
    }) => void
  ) {
    return supabase
      .channel(`notifications:${userId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "notifications",
          filter: `user_id=eq.${userId}`,
        },
        callback
      )
      .subscribe();
  },

  unsubscribeAll() {
    supabase.removeAllChannels();
  },
};
