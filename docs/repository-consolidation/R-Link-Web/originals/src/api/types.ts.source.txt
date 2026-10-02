/**
 * API 类型定义
 * 与后端 FastAPI 接口对应
 */

// ========== 插件相关类型 ==========

export interface PluginInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  binary_path: string;
  config_path?: string;
  icon?: string;
}

export interface PluginStatus {
  status: 'stopped' | 'running' | 'error';
  pid?: number;
  port?: number;
  uptime: number;
  memory_usage: number;
  cpu_usage: number;
  last_error?: string;
}

export interface PluginConfigRequest {
  config: Record<string, unknown>;
}

export interface PluginStartRequest {
  config?: Record<string, unknown>;
}

export interface PluginLogsResponse {
  plugin: string;
  lines: number;
  logs: string[];
}

export interface PluginHealthResponse {
  plugin: string;
  healthy: boolean;
}

export interface AllPluginStatusResponse {
  [pluginName: string]: PluginStatus;
}

// ========== 系统相关类型 ==========

export interface SystemInfo {
  hostname: string;
  system: string;
  release: string;
  version: string;
  machine: string;
  processor: string;
  python_version: string;
}

export interface SystemResources {
  cpu: {
    percent: number;
    count: number;
  };
  memory: {
    total: number;
    available: number;
    percent: number;
    used: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
    percent: number;
  };
}

export interface ProcessInfo {
  pid: number;
  name: string;
  username?: string;
  cpu_percent: number;
  memory_mb: number;
}

export interface SystemUptime {
  boot_time: number;
  uptime_seconds: number;
  uptime_human: string;
}

// ========== 通用类型 ==========

export interface ApiResponse<T = unknown> {
  status?: 'success' | 'error';
  message?: string;
  data?: T;
}

export interface ApiError {
  detail: string;
}

// ========== 前端扩展类型 ==========

export interface Plugin extends PluginInfo {
  status?: 'stopped' | 'running' | 'error';
  uptime?: number;
  memory_usage?: number;
  cpu_usage?: number;
  pid?: number;
  port?: number;
}

// 用于 UI 显示的插件状态
export interface PluginUI extends Plugin {
  rating?: number;
  downloads?: number;
  verified?: boolean;
  features?: string[];
  longDescription?: string;
}
