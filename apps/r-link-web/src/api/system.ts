/**
 * 系统相关 API
 * 对应后端 /api/system/ 路由
 */

import { http } from './client';
import { API_ENDPOINTS } from './config';
import type {
  SystemInfo,
  SystemResources,
  ProcessInfo,
  SystemUptime,
} from './types';

/**
 * 系统 API 类
 */
export class SystemApi {
  /**
   * 获取系统信息
   * GET /api/system/info
   */
  async getInfo(): Promise<SystemInfo> {
    return http.get<SystemInfo>(API_ENDPOINTS.system.info);
  }

  /**
   * 获取系统资源使用情况
   * GET /api/system/resources
   */
  async getResources(): Promise<SystemResources> {
    return http.get<SystemResources>(API_ENDPOINTS.system.resources);
  }

  /**
   * 获取系统进程列表
   * GET /api/system/processes
   */
  async getProcesses(): Promise<ProcessInfo[]> {
    return http.get<ProcessInfo[]>(API_ENDPOINTS.system.processes);
  }

  /**
   * 获取系统运行时间
   * GET /api/system/uptime
   */
  async getUptime(): Promise<SystemUptime> {
    return http.get<SystemUptime>(API_ENDPOINTS.system.uptime);
  }

  /**
   * 获取系统概览（组合方法）
   * 同时获取系统信息和资源使用情况
   */
  async getOverview(): Promise<SystemInfo & { resources: SystemResources; uptime: SystemUptime }> {
    const [info, resources, uptime] = await Promise.all([
      this.getInfo(),
      this.getResources(),
      this.getUptime(),
    ]);

    return {
      ...info,
      resources,
      uptime,
    };
  }
}

// 导出单例实例
export const systemApi = new SystemApi();
