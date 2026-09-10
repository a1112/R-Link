/**
 * Web Terminal 组件
 * 基于 xterm.js 实现 SSH 终端
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';
import { toast } from 'sonner';

// 导入 xterm 样式覆盖
import './Terminal.css';

export interface TerminalProps {
  /** WebSocket URL */
  wsUrl: string;
  /** SSH 主机 */
  host: string;
  /** SSH 端口 */
  port: number;
  /** SSH 用户名 */
  username: string;
  /** 密码 */
  password?: string;
  /** 私钥 */
  privateKey?: string;
  /** 私钥密码 */
  passphrase?: string;
  /** 连接成功回调 */
  onConnected?: () => void;
  /** 连接关闭回调 */
  onClosed?: (reason?: string) => void;
  /** 错误回调 */
  onError?: (error: string) => void;
  /** 是否自动连接 */
  autoConnect?: boolean;
  /** 主题颜色 */
  theme?: 'light' | 'dark';
  /** 字体大小 */
  fontSize?: number;
  /** 字体家族 */
  fontFamily?: string;
}

interface SSHMessage {
  type: 'auth' | 'data' | 'resize' | 'close' | 'connected' | 'error' | 'closed' | 'ping';
  data?: string;
  password?: string;
  private_key?: string;
  passphrase?: string;
  columns?: number;
  rows?: number;
  message?: string;
  host?: string;
  port?: number;
  username?: string;
}

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export const WebTerminal: React.FC<TerminalProps> = ({
  wsUrl,
  host,
  port,
  username,
  password,
  privateKey,
  passphrase,
  onConnected,
  onClosed,
  onError,
  autoConnect = false,
  theme = 'dark',
  fontSize = 14,
  fontFamily = 'Consolas, "Courier New", monospace',
}) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminalInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [error, setError] = useState<string | null>(null);

  // 创建终端实例
  const createTerminal = useCallback(() => {
    if (terminalInstanceRef.current) {
      return;
    }

    const terminal = new Terminal({
      theme: theme === 'dark' ? {
        background: '#0a0a0a',
        foreground: '#ffffff',
        cursor: '#ffffff',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#ffffff',
      } : {
        background: '#ffffff',
        foreground: '#000000',
        cursor: '#000000',
        black: '#000000',
        red: '#cd3131',
        green: '#00bc00',
        yellow: '#949800',
        blue: '#0451a5',
        magenta: '#bc05bc',
        cyan: '#0598bc',
        white: '#555555',
        brightBlack: '#666666',
        brightRed: '#cd3131',
        brightGreen: '#14ce14',
        brightYellow: '#b5ba00',
        brightBlue: '#0451a5',
        brightMagenta: '#bc05bc',
        brightCyan: '#0598bc',
        brightWhite: '#a5a5a5',
      },
      fontSize,
      fontFamily,
      cursorBlink: true,
      cursorStyle: 'block',
      scrollback: 1000,
      tabStopWidth: 4,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    terminalInstanceRef.current = terminal;
    fitAddonRef.current = fitAddon;

    if (terminalRef.current) {
      terminal.open(terminalRef.current);
      fitAddon.fit();
    }

    // 终端输入处理
    terminal.onData((data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'data',
          data: data,
        } as SSHMessage));
      }
    });

    // 终端尺寸变化处理
    terminal.onResize(({ cols, rows }) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'resize',
          columns: cols,
          rows: rows,
        } as SSHMessage));
      }
    });

    // 显示欢迎信息
    terminal.writeln('\x1b[1;36mR-Link Web SSH Terminal\x1b[0m');
    terminal.writeln(`Connecting to ${username}@${host}:${port}...\r\n`);
  }, [theme, fontSize, fontFamily, username, host, port]);

  // 连接 WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    setConnectionState('connecting');
    setError(null);

    try {
      const url = new URL(wsUrl);
      url.searchParams.set('host', host);
      url.searchParams.set('port', port.toString());
      url.searchParams.set('username', username);

      const ws = new WebSocket(url.toString());
      wsRef.current = ws;

      ws.onopen = () => {
        // 发送认证消息
        const authMessage: SSHMessage = {
          type: 'auth',
          password: password,
          private_key: privateKey,
          passphrase: passphrase,
          columns: terminalInstanceRef.current?.cols,
          rows: terminalInstanceRef.current?.rows,
        };
        ws.send(JSON.stringify(authMessage));
      };

      ws.onmessage = (event) => {
        try {
          const message: SSHMessage = JSON.parse(event.data);

          switch (message.type) {
            case 'connected':
              setConnectionState('connected');
              onConnected?.();
              if (terminalInstanceRef.current) {
                terminalInstanceRef.current.writeln(`\r\n\x1b[1;32m✔ Connected to ${message.username}@${message.host}:${message.port}\x1b[0m\r\n`);
              }
              break;

            case 'data':
              if (terminalInstanceRef.current) {
                terminalInstanceRef.current.write(message.data || '');
              }
              break;

            case 'error':
              setConnectionState('error');
              setError(message.message || 'Connection error');
              onError?.(message.message || 'Connection error');
              if (terminalInstanceRef.current) {
                terminalInstanceRef.current.writeln(`\r\n\x1b[1;31m✖ Error: ${message.message}\x1b[0m\r\n`);
              }
              break;

            case 'closed':
              setConnectionState('disconnected');
              onClosed?.();
              if (terminalInstanceRef.current) {
                terminalInstanceRef.current.writeln('\r\n\x1b[1;33m⚠ Connection closed\x1b[0m\r\n');
              }
              break;

            case 'ping':
              // 心跳响应，无需处理
              break;
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onerror = (event) => {
        setConnectionState('error');
        setError('WebSocket error');
        onError?.('WebSocket error');
      };

      ws.onclose = (event) => {
        setConnectionState('disconnected');
        onClosed?.(event.reason);
        wsRef.current = null;
      };

    } catch (e) {
      setConnectionState('error');
      setError(String(e));
      onError?.(String(e));
    }
  }, [wsUrl, host, port, username, password, privateKey, passphrase, onConnected, onClosed, onError]);

  // 断开连接
  const disconnect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'close' } as SSHMessage));
    }
    wsRef.current?.close();
    wsRef.current = null;
    setConnectionState('disconnected');
  }, []);

  // 重新连接
  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      connect();
    }, 500);
  }, [disconnect, connect]);

  // 清理
  useEffect(() => {
    return () => {
      disconnect();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [disconnect]);

  // 自动连接
  useEffect(() => {
    if (autoConnect && terminalRef.current) {
      createTerminal();
      connect();
    }
  }, [autoConnect, createTerminal, connect]);

  // 窗口大小变化时调整终端尺寸
  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 手动连接
  const handleConnect = () => {
    if (!terminalInstanceRef.current) {
      createTerminal();
    }
    connect();
  };

  // 获取连接状态显示
  const getConnectionStatus = () => {
    switch (connectionState) {
      case 'connecting':
        return { text: '连接中...', color: 'text-amber-500', icon: '⟳' };
      case 'connected':
        return { text: '已连接', color: 'text-emerald-500', icon: '●' };
      case 'error':
        return { text: '连接错误', color: 'text-red-500', icon: '✖' };
      default:
        return { text: '未连接', color: 'text-[var(--c-500)]', icon: '○' };
    }
  };

  const status = getConnectionStatus();

  return (
    <div className="web-terminal-container flex flex-col h-full bg-black rounded-lg overflow-hidden border border-[var(--c-800)]">
      {/* 终端头部 */}
      <div className="terminal-header flex items-center justify-between px-4 py-2 bg-[var(--c-900)] border-b border-[var(--c-800)]">
        <div className="flex items-center gap-3">
          <span className={`${status.color} text-sm flex items-center gap-1.5`}>
            <span className={connectionState === 'connecting' ? 'animate-spin' : ''}>{status.icon}</span>
            {status.text}
          </span>
          <span className="text-[var(--c-600)] text-sm">
            {username}@{host}:{port}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {connectionState === 'disconnected' && (
            <button
              onClick={handleConnect}
              className="px-3 py-1 text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded transition-colors"
            >
              连接
            </button>
          )}
          {connectionState === 'error' && (
            <button
              onClick={reconnect}
              className="px-3 py-1 text-xs bg-amber-600 hover:bg-amber-700 text-white rounded transition-colors"
            >
              重试
            </button>
          )}
          {(connectionState === 'connected' || connectionState === 'connecting') && (
            <button
              onClick={disconnect}
              className="px-3 py-1 text-xs bg-red-600 hover:bg-red-700 text-white rounded transition-colors"
            >
              断开
            </button>
          )}
        </div>
      </div>

      {/* 终端区域 */}
      <div
        ref={terminalRef}
        className="terminal-content flex-1 overflow-hidden"
        style={{ minHeight: 300 }}
      />

      {/* 错误提示 */}
      {error && (
        <div className="px-4 py-2 bg-red-500/10 border-t border-red-500/20">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}
    </div>
  );
};

export default WebTerminal;
