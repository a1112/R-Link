/**
 * HTTP 客户端
 * 封装 fetch API，提供统一的请求处理
 */

import { API_CONFIG } from './config';
import type { ApiError } from './types';

export interface RequestConfig extends RequestInit {
  params?: Record<string, string | number>;
  timeout?: number;
}

export class HttpClient {
  private baseURL: string;
  private defaultTimeout: number;

  constructor(baseURL: string = API_CONFIG.baseURL, timeout: number = API_CONFIG.timeout) {
    this.baseURL = baseURL;
    this.defaultTimeout = timeout;
  }

  /**
   * 构建完整 URL
   */
  private buildUrl(endpoint: string, params?: Record<string, string | number>): string {
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;

    if (!params) {
      return url;
    }

    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      searchParams.append(key, String(value));
    });

    const queryString = searchParams.toString();
    return queryString ? `${url}?${queryString}` : url;
  }

  /**
   * 创建超时控制器
   */
  private createTimeoutController(timeout: number): [AbortController, number] {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    return [controller, timeoutId];
  }

  /**
   * 处理响应
   */
  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;

      try {
        const errorData = (await response.json()) as ApiError;
        if (errorData.detail) {
          errorMessage = errorData.detail;
        }
      } catch {
        // JSON 解析失败，使用默认错误消息
      }

      throw new Error(errorMessage);
    }

    // 204 No Content 不需要解析 JSON
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  /**
   * 发送请求
   */
  async request<T>(endpoint: string, config: RequestConfig = {}): Promise<T> {
    const { params, timeout = this.defaultTimeout, ...fetchConfig } = config;
    const url = this.buildUrl(endpoint, params);
    const [controller, timeoutId] = this.createTimeoutController(timeout);

    try {
      const response = await fetch(url, {
        ...fetchConfig,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...fetchConfig.headers,
        },
      });

      return await this.handleResponse<T>(response);
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new Error(`请求超时: ${timeout}ms`);
        }
        throw error;
      }
      throw new Error('未知错误');
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * GET 请求
   */
  async get<T>(endpoint: string, config?: RequestConfig): Promise<T> {
    return this.request<T>(endpoint, { ...config, method: 'GET' });
  }

  /**
   * POST 请求
   */
  async post<T>(endpoint: string, data?: unknown, config?: RequestConfig): Promise<T> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * PUT 请求
   */
  async put<T>(endpoint: string, data?: unknown, config?: RequestConfig): Promise<T> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * PATCH 请求
   */
  async patch<T>(endpoint: string, data?: unknown, config?: RequestConfig): Promise<T> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * DELETE 请求
   */
  async delete<T>(endpoint: string, config?: RequestConfig): Promise<T> {
    return this.request<T>(endpoint, { ...config, method: 'DELETE' });
  }
}

// 创建默认实例
export const http = new HttpClient();
