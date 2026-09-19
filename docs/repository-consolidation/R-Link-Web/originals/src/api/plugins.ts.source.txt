/**
 * 插件相关 API
 * 对应后端 /api/plugins/ 路由
 */

import { http } from './client';
import { API_ENDPOINTS } from './config';
import type {
  PluginInfo,
  PluginStatus,
  PluginConfigRequest,
  PluginStartRequest,
  PluginLogsResponse,
  PluginHealthResponse,
  AllPluginStatusResponse,
  ApiResponse,
} from './types';

/**
 * 插件 API 类
 */
export class PluginsApi {
  /**
   * 获取所有插件列表
   * GET /api/plugins/
   */
  async list(): Promise<PluginInfo[]> {
    return http.get<PluginInfo[]>(API_ENDPOINTS.plugins.list);
  }

  /**
   * 获取指定插件信息
   * GET /api/plugins/{name}
   */
  async get(name: string): Promise<PluginInfo> {
    return http.get<PluginInfo>(API_ENDPOINTS.plugins.detail(name));
  }

  /**
   * 启动插件
   * POST /api/plugins/{name}/start
   */
  async start(name: string, config?: Record<string, unknown>): Promise<ApiResponse> {
    const data: PluginStartRequest = config ? { config } : undefined;
    return http.post<ApiResponse>(API_ENDPOINTS.plugins.start(name), data);
  }

  /**
   * 停止插件
   * POST /api/plugins/{name}/stop
   */
  async stop(name: string): Promise<ApiResponse> {
    return http.post<ApiResponse>(API_ENDPOINTS.plugins.stop(name));
  }

  /**
   * 重启插件
   * POST /api/plugins/{name}/restart
   */
  async restart(name: string): Promise<ApiResponse> {
    return http.post<ApiResponse>(API_ENDPOINTS.plugins.restart(name));
  }

  /**
   * 获取插件状态
   * GET /api/plugins/{name}/status
   */
  async getStatus(name: string): Promise<PluginStatus> {
    return http.get<PluginStatus>(API_ENDPOINTS.plugins.status(name));
  }

  /**
   * 获取所有插件状态
   * GET /api/plugins/status/all
   */
  async getAllStatus(): Promise<AllPluginStatusResponse> {
    return http.get<AllPluginStatusResponse>(API_ENDPOINTS.plugins.statusAll);
  }

  /**
   * 获取插件配置
   * GET /api/plugins/{name}/config
   */
  async getConfig(name: string): Promise<Record<string, unknown>> {
    return http.get<Record<string, unknown>>(API_ENDPOINTS.plugins.config(name));
  }

  /**
   * 设置插件配置
   * PUT /api/plugins/{name}/config
   */
  async setConfig(name: string, config: Record<string, unknown>): Promise<ApiResponse> {
    const data: PluginConfigRequest = { config };
    return http.put<ApiResponse>(API_ENDPOINTS.plugins.config(name), data);
  }

  /**
   * 获取插件日志
   * GET /api/plugins/{name}/logs
   */
  async getLogs(name: string, lines: number = 100): Promise<PluginLogsResponse> {
    return http.get<PluginLogsResponse>(API_ENDPOINTS.plugins.logs(name, lines));
  }

  /**
   * 检查插件健康状态
   * GET /api/plugins/{name}/health
   */
  async checkHealth(name: string): Promise<PluginHealthResponse> {
    return http.get<PluginHealthResponse>(API_ENDPOINTS.plugins.health(name));
  }

  /**
   * 获取插件列表及状态（组合方法）
   * 同时获取插件列表和状态信息
   */
  async listWithStatus(): Promise<Array<PluginInfo & { status: PluginStatus }>> {
    const [plugins, allStatus] = await Promise.all([
      this.list(),
      this.getAllStatus(),
    ]);

    return plugins.map((plugin) => ({
      ...plugin,
      status: allStatus[plugin.name] || {
        status: 'stopped',
        uptime: 0,
        memory_usage: 0,
        cpu_usage: 0,
      },
    }));
  }
}

// 导出单例实例
export const pluginsApi = new PluginsApi();
