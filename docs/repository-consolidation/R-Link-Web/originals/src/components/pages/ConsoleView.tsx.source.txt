/**
 * Web 控制台页面
 *
 * 使用 ttyd.exe 提供浏览器终端访问
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Terminal as TerminalIcon,
  Play,
  Square,
  RotateCcw,
  Settings,
  Maximize2,
  Minimize2,
  Monitor,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";

type ConsoleStatus = "stopped" | "starting" | "running" | "error";

interface ConsoleStatusResponse {
  status: string;
  pid?: number;
  port?: number;
  console_url?: string;
  ttyd_running?: boolean;
}

interface ApiResponse<T = any> {
  success?: boolean;
  error?: string;
  data?: T;
}

// API 基础 URL
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const ConsoleView: React.FC = () => {
  const [status, setStatus] = useState<ConsoleStatus>("stopped");
  const [consoleUrl, setConsoleUrl] = useState<string>("/console");
  const [port, setPort] = useState(7681);
  const [command, setCommand] = useState("cmd.exe");
  const [fullscreen, setFullscreen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const iframeRef = useRef<HTMLIFrameElement>(null);

  // 获取控制台状态
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/console/status`);
      if (response.ok) {
        const data: ConsoleStatusResponse = await response.json();
        if (data.ttyd_running) {
          setStatus("running");
          setConsoleUrl(data.console_url || "/console");
          setPort(data.port || 7681);
        } else {
          setStatus("stopped");
        }
      }
    } catch (error) {
      console.error("Failed to fetch console status:", error);
    }
  }, []);

  // 启动控制台
  const startConsole = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/console/start`, {
        method: "POST",
      });
      const result: ApiResponse = await response.json();

      if (result.success || !result.error) {
        setStatus("running");
        toast.success("控制台服务已启动");

        // 刷新 iframe
        setTimeout(() => {
          if (iframeRef.current) {
            iframeRef.current.src = iframeRef.current.src;
          }
        }, 2000);

        await fetchStatus();
      } else {
        setStatus("error");
        toast.error(result.error || "启动失败");
      }
    } catch (error) {
      setStatus("error");
      toast.error("启动控制台服务失败");
    } finally {
      setIsLoading(false);
    }
  };

  // 停止控制台
  const stopConsole = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/console/stop`, {
        method: "POST",
      });
      const result: ApiResponse = await response.json();

      if (result.success || !result.error) {
        setStatus("stopped");
        toast.success("控制台服务已停止");
      } else {
        toast.error(result.error || "停止失败");
      }
    } catch (error) {
      toast.error("停止控制台服务失败");
    } finally {
      setIsLoading(false);
    }
  };

  // 重启控制台
  const restartConsole = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/console/restart`, {
        method: "POST",
      });
      const result: ApiResponse = await response.json();

      if (result.success || !result.error) {
        setStatus("running");
        toast.success("控制台服务已重启");

        // 刷新 iframe
        setTimeout(() => {
          if (iframeRef.current) {
            iframeRef.current.src = iframeRef.current.src;
          }
        }, 2000);

        await fetchStatus();
      } else {
        setStatus("error");
        toast.error(result.error || "重启失败");
      }
    } catch (error) {
      setStatus("error");
      toast.error("重启控制台服务失败");
    } finally {
      setIsLoading(false);
    }
  };

  // 更新配置
  const updateConfig = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/console/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, port, enable_nginx_proxy: true }),
      });
      const result: ApiResponse = await response.json();

      if (result.success) {
        toast.success("配置已更新");
        setShowSettings(false);
        // 重启服务以应用新配置
        if (status === "running") {
          await restartConsole();
        }
      } else {
        toast.error(result.error || "更新配置失败");
      }
    } catch (error) {
      toast.error("更新配置失败");
    } finally {
      setIsLoading(false);
    }
  };

  // 初始化时获取状态
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // 定期检查状态
  useEffect(() => {
    if (status === "running") {
      const interval = setInterval(fetchStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [status, fetchStatus]);

  // 全屏切换
  const toggleFullscreen = () => {
    setFullscreen(!fullscreen);
  };

  // 获取状态显示
  const getStatusDisplay = () => {
    switch (status) {
      case "starting":
        return {
          icon: Loader2,
          color: "text-amber-500",
          bg: "bg-amber-500/10",
          label: "启动中",
          animate: true,
        };
      case "running":
        return {
          icon: CheckCircle2,
          color: "text-emerald-500",
          bg: "bg-emerald-500/10",
          label: "运行中",
        };
      case "error":
        return {
          icon: XCircle,
          color: "text-red-500",
          bg: "bg-red-500/10",
          label: "错误",
        };
      default:
        return {
          icon: XCircle,
          color: "text-[var(--c-500)]",
          bg: "bg-[var(--c-800)]",
          label: "已停止",
        };
    }
  };

  const statusDisplay = getStatusDisplay();
  const StatusIcon = statusDisplay.icon;

  // 构建控制台 URL
  const getConsoleUrl = () => {
    // 如果 nginx 代理启用，使用相对路径
    return consoleUrl || `http://localhost:${port}`;
  };

  return (
    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">Web 控制台</h2>
            <p className="text-[var(--c-500)] text-sm">使用 ttyd.exe 提供浏览器终端访问</p>
          </div>

          {/* 状态指示 */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${statusDisplay.bg}`}>
            <StatusIcon
              size={16}
              className={statusDisplay.color + (statusDisplay.animate ? " animate-spin" : "")}
            />
            <span className={`text-sm font-medium ${statusDisplay.color}`}>
              {status === "starting" ? "启动中..." : statusDisplay.label}
            </span>
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center gap-2">
          {status === "stopped" || status === "error" ? (
            <button
              onClick={startConsole}
              disabled={isLoading}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-800 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              {isLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Play size={16} />
              )}
              启动
            </button>
          ) : (
            <>
              <button
                onClick={stopConsole}
                disabled={isLoading}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                {isLoading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Square size={16} />
                )}
                停止
              </button>
              <button
                onClick={restartConsole}
                disabled={isLoading}
                className="px-4 py-2 bg-[var(--c-800)] hover:bg-[var(--c-700)] disabled:bg-[var(--c-900)] text-[var(--c-200)] rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                {isLoading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <RotateCcw size={16} />
                )}
                重启
              </button>
            </>
          )}

          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors"
            title="设置"
          >
            <Settings size={18} />
          </button>

          <button
            onClick={toggleFullscreen}
            className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors"
            title={fullscreen ? "退出全屏" : "全屏"}
          >
            {fullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
          </button>
        </div>
      </div>

      {/* 设置面板 */}
      {showSettings && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4"
        >
          <h3 className="text-sm font-semibold text-[var(--c-200)] mb-4">控制台设置</h3>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-xs text-[var(--c-500)] mb-1">终端命令</label>
              <input
                type="text"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] focus:outline-none focus:border-blue-500"
                placeholder="cmd.exe"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--c-500)] mb-1">监听端口</label>
              <input
                type="number"
                value={port}
                onChange={(e) => setPort(parseInt(e.target.value) || 7681)}
                className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={updateConfig}
                className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                应用配置
              </button>
            </div>
          </div>
          <div className="text-xs text-[var(--c-600)]">
            <p>• 修改配置后需要重启服务才能生效</p>
            <p>• Windows 推荐使用 cmd.exe 或 powershell.exe</p>
            <p>• Linux 可使用 bash、zsh 等</p>
          </div>
        </motion.div>
      )}

      {/* 终端容器 */}
      <div
        className={`bg-black rounded-lg overflow-hidden border border-[var(--c-800)] ${
          fullscreen ? "fixed inset-4 z-50" : "h-[calc(100vh-200px)]"
        }`}
      >
        {status === "running" ? (
          <iframe
            ref={iframeRef}
            src={getConsoleUrl()}
            className="w-full h-full"
            title="Web Console"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
            allowFullScreen
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-[var(--c-600)]">
            <Monitor size={64} className="mb-4 opacity-50" />
            <p className="text-lg mb-2">控制台服务未运行</p>
            <p className="text-sm mb-4">点击上方"启动"按钮开始使用</p>
            <div className="flex items-center gap-2 text-xs">
              <TerminalIcon size={14} />
              <span>需要安装 ttyd.exe</span>
            </div>
          </div>
        )}
      </div>

      {/* 信息卡片 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[var(--c-500)] text-sm">访问地址</span>
            <TerminalIcon size={16} className="text-blue-500" />
          </div>
          <div className="text-sm font-mono text-[var(--c-200)]">{getConsoleUrl()}</div>
        </div>
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[var(--c-500)] text-sm">监听端口</span>
            <CheckCircle2 size={16} className="text-emerald-500" />
          </div>
          <div className="text-sm font-mono text-[var(--c-200)]">{port}</div>
        </div>
        <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[var(--c-500)] text-sm">终端命令</span>
            <TerminalIcon size={16} className="text-purple-500" />
          </div>
          <div className="text-sm font-mono text-[var(--c-200)]">{command}</div>
        </div>
      </div>
    </div>
  );
};

export default ConsoleView;
