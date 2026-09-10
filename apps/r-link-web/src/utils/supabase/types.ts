/**
 * Supabase 数据库类型定义
 * 自动生成 - 对应 001_initial_tables.sql
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      // ============================================
      // profiles - 用户扩展表
      // ============================================
      profiles: {
        Row: {
          id: string
          email: string
          username: string | null
          full_name: string | null
          avatar_url: string | null
          bio: string | null
          role: 'admin' | 'user' | 'guest'
          preferences: Json
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          email: string
          username?: string | null
          full_name?: string | null
          avatar_url?: string | null
          bio?: string | null
          role?: 'admin' | 'user' | 'guest'
          preferences?: Json
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          email?: string
          username?: string | null
          full_name?: string | null
          avatar_url?: string | null
          bio?: string | null
          role?: 'admin' | 'user' | 'guest'
          preferences?: Json
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // plugin_configs - 插件配置表
      // ============================================
      plugin_configs: {
        Row: {
          id: string
          user_id: string
          plugin_id: string
          plugin_name: string | null
          config: Json
          enabled: boolean
          auto_start: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          plugin_id: string
          plugin_name?: string | null
          config?: Json
          enabled?: boolean
          auto_start?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          plugin_id?: string
          plugin_name?: string | null
          config?: Json
          enabled?: boolean
          auto_start?: boolean
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // plugin_market - 插件市场表
      // ============================================
      plugin_market: {
        Row: {
          id: string
          plugin_id: string
          name: string
          description: string | null
          version: string
          author: string | null
          category: string | null
          icon_url: string | null
          homepage_url: string | null
          repository_url: string | null
          download_url: string | null
          file_size: number | null
          min_app_version: string | null
          tags: string[]
          screenshots: string[]
          downloads: number
          rating: number
          rating_count: number
          is_builtin: boolean
          is_official: boolean
          status: 'active' | 'deprecated' | 'removed'
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          plugin_id: string
          name: string
          description?: string | null
          version?: string
          author?: string | null
          category?: string | null
          icon_url?: string | null
          homepage_url?: string | null
          repository_url?: string | null
          download_url?: string | null
          file_size?: number | null
          min_app_version?: string | null
          tags?: string[]
          screenshots?: string[]
          downloads?: number
          rating?: number
          rating_count?: number
          is_builtin?: boolean
          is_official?: boolean
          status?: 'active' | 'deprecated' | 'removed'
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          plugin_id?: string
          name?: string
          description?: string | null
          version?: string
          author?: string | null
          category?: string | null
          icon_url?: string | null
          homepage_url?: string | null
          repository_url?: string | null
          download_url?: string | null
          file_size?: number | null
          min_app_version?: string | null
          tags?: string[]
          screenshots?: string[]
          downloads?: number
          rating?: number
          rating_count?: number
          is_builtin?: boolean
          is_official?: boolean
          status?: 'active' | 'deprecated' | 'removed'
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // plugin_reviews - 插件评论表
      // ============================================
      plugin_reviews: {
        Row: {
          id: string
          plugin_id: string
          user_id: string
          rating: number
          title: string | null
          content: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          plugin_id: string
          user_id: string
          rating: number
          title?: string | null
          content?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          plugin_id?: string
          user_id?: string
          rating?: number
          title?: string | null
          content?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // user_settings - 用户设置表
      // ============================================
      user_settings: {
        Row: {
          id: string
          user_id: string
          theme: 'dark' | 'light' | 'auto'
          language: string
          timezone: string
          notifications_enabled: boolean
          email_notifications: boolean
          desktop_notifications: boolean
          auto_start_plugins: string[]
          dashboard_layout: Json
          sidebar_collapsed: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          theme?: 'dark' | 'light' | 'auto'
          language?: string
          timezone?: string
          notifications_enabled?: boolean
          email_notifications?: boolean
          desktop_notifications?: boolean
          auto_start_plugins?: string[]
          dashboard_layout?: Json
          sidebar_collapsed?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          theme?: 'dark' | 'light' | 'auto'
          language?: string
          timezone?: string
          notifications_enabled?: boolean
          email_notifications?: boolean
          desktop_notifications?: boolean
          auto_start_plugins?: string[]
          dashboard_layout?: Json
          sidebar_collapsed?: boolean
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // remote_connections - 远程连接表
      // ============================================
      remote_connections: {
        Row: {
          id: string
          user_id: string
          name: string
          type: 'ssh' | 'rdp' | 'vnc' | 'sftp' | 'ftp' | 'custom'
          host: string
          port: number | null
          username: string | null
          password_encrypted: string | null
          private_key_encrypted: string | null
          auth_method: 'password' | 'key' | 'both'
          tags: string[]
          description: string | null
          group_name: string | null
          is_favorite: boolean
          last_connected_at: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          type?: 'ssh' | 'rdp' | 'vnc' | 'sftp' | 'ftp' | 'custom'
          host: string
          port?: number | null
          username?: string | null
          password_encrypted?: string | null
          private_key_encrypted?: string | null
          auth_method?: 'password' | 'key' | 'both'
          tags?: string[]
          description?: string | null
          group_name?: string | null
          is_favorite?: boolean
          last_connected_at?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          type?: 'ssh' | 'rdp' | 'vnc' | 'sftp' | 'ftp' | 'custom'
          host?: string
          port?: number | null
          username?: string | null
          password_encrypted?: string | null
          private_key_encrypted?: string | null
          auth_method?: 'password' | 'key' | 'both'
          tags?: string[]
          description?: string | null
          group_name?: string | null
          is_favorite?: boolean
          last_connected_at?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // connection_history - 连接历史表
      // ============================================
      connection_history: {
        Row: {
          id: string
          user_id: string
          connection_id: string | null
          connection_name: string | null
          status: 'connected' | 'disconnected' | 'failed'
          error_message: string | null
          duration_seconds: number | null
          connected_at: string
          disconnected_at: string | null
        }
        Insert: {
          id?: string
          user_id: string
          connection_id?: string | null
          connection_name?: string | null
          status?: 'connected' | 'disconnected' | 'failed'
          error_message?: string | null
          duration_seconds?: number | null
          connected_at?: string
          disconnected_at?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          connection_id?: string | null
          connection_name?: string | null
          status?: 'connected' | 'disconnected' | 'failed'
          error_message?: string | null
          duration_seconds?: number | null
          connected_at?: string
          disconnected_at?: string | null
        }
      }
      // ============================================
      // frp_configs - FRP 配置表
      // ============================================
      frp_configs: {
        Row: {
          id: string
          user_id: string
          name: string
          server_addr: string
          server_port: number
          auth_token: string | null
          proxies: Json
          enabled: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          server_addr: string
          server_port?: number
          auth_token?: string | null
          proxies?: Json
          enabled?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          server_addr?: string
          server_port?: number
          auth_token?: string | null
          proxies?: Json
          enabled?: boolean
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // storage_mappings - 存储映射表
      // ============================================
      storage_mappings: {
        Row: {
          id: string
          user_id: string
          name: string
          type: 'local' | 's3' | 'webdav' | 'onedrive' | 'google'
          config: Json
          mount_point: string | null
          enabled: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          type?: 'local' | 's3' | 'webdav' | 'onedrive' | 'google'
          config?: Json
          mount_point?: string | null
          enabled?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          type?: 'local' | 's3' | 'webdav' | 'onedrive' | 'google'
          config?: Json
          mount_point?: string | null
          enabled?: boolean
          created_at?: string
          updated_at?: string
        }
      }
      // ============================================
      // notifications - 通知表
      // ============================================
      notifications: {
        Row: {
          id: string
          user_id: string
          type: 'info' | 'success' | 'warning' | 'error'
          title: string
          message: string | null
          action_url: string | null
          action_label: string | null
          read: boolean
          created_at: string
          expires_at: string | null
        }
        Insert: {
          id?: string
          user_id: string
          type?: 'info' | 'success' | 'warning' | 'error'
          title: string
          message?: string | null
          action_url?: string | null
          action_label?: string | null
          read?: boolean
          created_at?: string
          expires_at?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          type?: 'info' | 'success' | 'warning' | 'error'
          title?: string
          message?: string | null
          action_url?: string | null
          action_label?: string | null
          read?: boolean
          created_at?: string
          expires_at?: string | null
        }
      }
      // ============================================
      // api_keys - API 密钥表
      // ============================================
      api_keys: {
        Row: {
          id: string
          user_id: string
          name: string
          key_hash: string
          scopes: string[]
          last_used_at: string | null
          expires_at: string | null
          is_active: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          key_hash: string
          scopes?: string[]
          last_used_at?: string | null
          expires_at?: string | null
          is_active?: boolean
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          key_hash?: string
          scopes?: string[]
          last_used_at?: string | null
          expires_at?: string | null
          is_active?: boolean
          created_at?: string
        }
      }
      // ============================================
      // files - 文件表
      // ============================================
      files: {
        Row: {
          id: string
          user_id: string
          name: string
          file_path: string
          file_size: number | null
          mime_type: string | null
          storage_type: 'supabase' | 's3' | 'local'
          bucket_name: string
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          file_path: string
          file_size?: number | null
          mime_type?: string | null
          storage_type?: 'supabase' | 's3' | 'local'
          bucket_name?: string
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          file_path?: string
          file_size?: number | null
          mime_type?: string | null
          storage_type?: 'supabase' | 's3' | 'local'
          bucket_name?: string
          created_at?: string
        }
      }
      // ============================================
      // audit_logs - 审计日志表
      // ============================================
      audit_logs: {
        Row: {
          id: string
          user_id: string | null
          action: string
          resource_type: string | null
          resource_id: string | null
          details: Json
          ip_address: string | null
          user_agent: string | null
          created_at: string
        }
        Insert: {
          id?: string
          user_id?: string | null
          action: string
          resource_type?: string | null
          resource_id?: string | null
          details?: Json
          ip_address?: string | null
          user_agent?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string | null
          action?: string
          resource_type?: string | null
          resource_id?: string | null
          details?: Json
          ip_address?: string | null
          user_agent?: string | null
          created_at?: string
        }
      }
      // ============================================
      // system_config - 系统配置表
      // ============================================
      system_config: {
        Row: {
          key: string
          value: Json
          description: string | null
          updated_by: string | null
          updated_at: string
        }
        Insert: {
          key: string
          value: Json
          description?: string | null
          updated_by?: string | null
          updated_at?: string
        }
        Update: {
          key?: string
          value?: Json
          description?: string | null
          updated_by?: string | null
          updated_at?: string
        }
      }
    }
    Views: {
      user_stats: {
        Row: {
          user_id: string
          username: string | null
          active_plugins: number | null
          total_connections: number | null
          recent_connections: number | null
          member_since: string
        }
      }
    }
    Functions: {
      _test_connection_: {
        Args: { row: Json }
        Returns: Json
      }
    }
    Enums: {
      user_role: 'admin' | 'user' | 'guest'
      plugin_status: 'active' | 'inactive' | 'error'
      connection_type: 'ssh' | 'rdp' | 'vnc' | 'sftp' | 'ftp' | 'custom'
      auth_method: 'password' | 'key' | 'both'
      notification_type: 'info' | 'success' | 'warning' | 'error'
    }
  }
}
