/**
 * SSH 终端页面
 *
 * 提供管理 SSH 连接和 Web 终端功能
 */

import React, { useState, useMemo, useCallback } from "react";
import {
  Terminal as TerminalIcon,
  Plus,
  Trash2,
  Edit,
  Copy,
  ExternalLink,
  Server,
  Lock,
  Eye,
  EyeOff,
  Save,
  X,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Terminal } from "../terminal";

interface SSHConnection {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  password?: string;
  privateKey?: string;
  passphrase?: string;
  group?: string;
  tags?: string[];
  createdAt: string;
  lastConnected?: string;
}

// 模拟保存的连接
const mockConnections: SSHConnection[] = [
  {
    id: 'conn-001',
    name: '生产服务器',
    host: '192.168.1.100',
    port: 22,
    username: 'root',
    group: '生产环境',
    tags: ['linux', 'production'],
    createdAt: '2026-01-10',
    lastConnected: '2026-01-20',
  },
  {
    id: 'conn-002',
    name: '开发服务器',
    host: 'localhost',
    port: 2222,
    username: 'dev',
    group: '开发环境',
    tags: ['local', 'development'],
    createdAt: '2026-01-08',
    lastConnected: '2026-01-19',
  },
];

type ViewMode = 'list' | 'terminal';

interface ConnectionForm {
  name: string;
  host: string;
  port: number;
  username: string;
  password: string;
  privateKey: string;
  passphrase: string;
  group: string;
}

const emptyForm: ConnectionForm = {
  name: '',
  host: '',
  port: 22,
  username: '',
  password: '',
  privateKey: '',
  passphrase: '',
  group: '',
};

export const SSHView: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [connections, setConnections] = useState<SSHConnection[]>(mockConnections);
  const [selectedConnection, setSelectedConnection] = useState<SSHConnection | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingConnection, setEditingConnection] = useState<SSHConnection | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState<ConnectionForm>(emptyForm);
  const [showKeyInput, setShowKeyInput] = useState(false);

  // 获取 WebSocket URL
  const getWsUrl = useCallback((conn: SSHConnection) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_API_HOST || window.location.hostname;
    const port = import.meta.env.VITE_API_PORT || '8000';
    return `${protocol}//${host}:${port}/api/ssh/connect`;
  }, []);

  // 分组后的连接
  const groupedConnections = useMemo(() => {
    const groups: Record<string, SSHConnection[]> = {};
    connections.forEach(conn => {
      const group = conn.group || '未分组';
      if (!groups[group]) {
        groups[group] = [];
      }
      groups[group].push(conn);
    });
    return groups;
  }, [connections]);

  // 打开终端
  const handleOpenTerminal = (conn: SSHConnection) => {
    setSelectedConnection(conn);
    setViewMode('terminal');
  };

  // 返回列表
  const handleBackToList = () => {
    setViewMode('list');
    setSelectedConnection(null);
  };

  // 新建连接
  const handleNewConnection = () => {
    setEditingConnection(null);
    setFormData(emptyForm);
    setShowForm(true);
  };

  // 编辑连接
  const handleEditConnection = (conn: SSHConnection, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingConnection(conn);
    setFormData({
      name: conn.name,
      host: conn.host,
      port: conn.port,
      username: conn.username,
      password: conn.password || '',
      privateKey: conn.privateKey || '',
      passphrase: conn.passphrase || '',
      group: conn.group || '',
    });
    setShowKeyInput(!!conn.privateKey);
    setShowForm(true);
  };

  // 复制连接
  const handleCopyConnection = (conn: SSHConnection, e: React.MouseEvent) => {
    e.stopPropagation();
    const newConn: SSHConnection = {
      ...conn,
      id: `conn-${Date.now()}`,
      name: `${conn.name} (副本)`,
      createdAt: new Date().toISOString().split('T')[0],
      lastConnected: undefined,
    };
    setConnections([...connections, newConn]);
    toast.success('连接已复制');
  };

  // 删除连接
  const handleDeleteConnection = (conn: SSHConnection, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`确定要删除连接 "${conn.name}" 吗？`)) {
      setConnections(connections.filter(c => c.id !== conn.id));
      toast.success('连接已删除');
    }
  };

  // 保存表单
  const handleSaveForm = () => {
    if (!formData.name || !formData.host || !formData.username) {
      toast.error('请填写必填字段');
      return;
    }

    if (editingConnection) {
      // 更新现有连接
      setConnections(connections.map(conn =>
        conn.id === editingConnection.id
          ? {
              ...conn,
              name: formData.name,
              host: formData.host,
              port: formData.port,
              username: formData.username,
              password: formData.password || undefined,
              privateKey: showKeyInput ? formData.privateKey : undefined,
              passphrase: showKeyInput ? formData.passphrase : undefined,
              group: formData.group || undefined,
            }
          : conn
      ));
      toast.success('连接已更新');
    } else {
      // 创建新连接
      const newConn: SSHConnection = {
        id: `conn-${Date.now()}`,
        name: formData.name,
        host: formData.host,
        port: formData.port,
        username: formData.username,
        password: formData.password || undefined,
        privateKey: showKeyInput ? formData.privateKey : undefined,
        passphrase: showKeyInput ? formData.passphrase : undefined,
        group: formData.group || undefined,
        createdAt: new Date().toISOString().split('T')[0],
      };
      setConnections([...connections, newConn]);
      toast.success('连接已创建');
    }

    setShowForm(false);
    setFormData(emptyForm);
    setEditingConnection(null);
  };

  // 快速连接（临时连接）
  const [quickConnect, setQuickConnect] = useState(false);

  if (viewMode === 'terminal' && selectedConnection) {
    const wsUrl = getWsUrl(selectedConnection);

    return (
      <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
        {/* 顶部导航栏 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={handleBackToList}
              className="p-2 hover:bg-[var(--c-800)] rounded-lg text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors"
              title="返回列表"
            >
              <X size={20} />
            </button>
            <div>
              <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">{selectedConnection.name}</h2>
              <p className="text-[var(--c-500)] text-sm">
                {selectedConnection.username}@{selectedConnection.host}:{selectedConnection.port}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 text-sm text-[var(--c-500)]">
              <Server size={16} />
              <span>{selectedConnection.host}</span>
            </div>
          </div>
        </div>

        {/* 终端 */}
        <div className="flex-1 min-h-[500px]">
          <Terminal
            wsUrl={wsUrl}
            host={selectedConnection.host}
            port={selectedConnection.port}
            username={selectedConnection.username}
            password={selectedConnection.password}
            privateKey={selectedConnection.privateKey}
            passphrase={selectedConnection.passphrase}
            autoConnect={true}
            onConnected={() => toast.success('SSH 连接已建立')}
            onClosed={(reason) => toast.info(reason || 'SSH 连接已关闭')}
            onError={(error) => toast.error(`SSH 错误: ${error}`)}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">SSH 终端</h2>
          <p className="text-[var(--c-500)] text-sm">管理 SSH 连接并在浏览器中使用终端</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setQuickConnect(true)}
            className="px-4 py-2 bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            <TerminalIcon size={16} />
            快速连接
          </button>
          <button
            onClick={handleNewConnection}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            <Plus size={16} />
            新建连接
          </button>
        </div>
      </div>

      {/* 快速连接面板 */}
      <AnimatePresence>
        {quickConnect && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4"
          >
            <h3 className="text-sm font-semibold text-[var(--c-200)] mb-4">快速连接</h3>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-[var(--c-500)] mb-1">主机</label>
                <input
                  type="text"
                  placeholder="192.168.1.1"
                  className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                  defaultValue={formData.host}
                  onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--c-500)] mb-1">端口</label>
                <input
                  type="number"
                  placeholder="22"
                  className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                  defaultValue={formData.port}
                  onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) || 22 })}
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--c-500)] mb-1">用户名</label>
                <input
                  type="text"
                  placeholder="root"
                  className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                  defaultValue={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                />
              </div>
              <div className="flex items-end gap-2">
                <button
                  onClick={() => {
                    if (!formData.host || !formData.username) {
                      toast.error('请填写主机和用户名');
                      return;
                    }
                    const tempConn: SSHConnection = {
                      id: 'temp',
                      name: formData.host,
                      host: formData.host,
                      port: formData.port,
                      username: formData.username,
                      password: formData.password || undefined,
                      createdAt: new Date().toISOString().split('T')[0],
                    };
                    setSelectedConnection(tempConn);
                    setViewMode('terminal');
                    setQuickConnect(false);
                  }}
                  className="flex-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
                >
                  <ExternalLink size={16} />
                  连接
                </button>
                <button
                  onClick={() => setQuickConnect(false)}
                  className="px-3 py-2 bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] rounded-lg text-sm transition-colors"
                >
                  取消
                </button>
              </div>
            </div>
            {/* 可选：密码输入 */}
            <div className="mt-4">
              <label className="flex items-center gap-2 text-sm text-[var(--c-500)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={showPassword}
                  onChange={(e) => setShowPassword(e.target.checked)}
                  className="rounded"
                />
                使用密码认证
              </label>
              {showPassword && (
                <input
                  type="password"
                  placeholder="密码（可选）"
                  className="mt-2 w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 连接表单弹窗 */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
            onClick={() => setShowForm(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-2xl p-6 w-full max-w-lg"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-[var(--c-100)]">
                  {editingConnection ? '编辑连接' : '新建连接'}
                </h3>
                <button
                  onClick={() => setShowForm(false)}
                  className="p-1 hover:bg-[var(--c-800)] rounded text-[var(--c-500)] hover:text-[var(--c-200)]"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-[var(--c-500)] mb-1">连接名称 *</label>
                  <input
                    type="text"
                    placeholder="我的服务器"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-[var(--c-500)] mb-1">主机 *</label>
                    <input
                      type="text"
                      placeholder="192.168.1.1"
                      value={formData.host}
                      onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                      className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--c-500)] mb-1">端口</label>
                    <input
                      type="number"
                      value={formData.port}
                      onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) || 22 })}
                      className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-[var(--c-500)] mb-1">用户名 *</label>
                  <input
                    type="text"
                    placeholder="root"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs text-[var(--c-500)] mb-1">分组</label>
                  <input
                    type="text"
                    placeholder="生产环境"
                    value={formData.group}
                    onChange={(e) => setFormData({ ...formData, group: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm text-[var(--c-500)] cursor-pointer mb-2">
                    <input
                      type="checkbox"
                      checked={showKeyInput}
                      onChange={(e) => setShowKeyInput(e.target.checked)}
                      className="rounded"
                    />
                    使用私钥认证
                  </label>

                  {showKeyInput ? (
                    <div className="space-y-3">
                      <textarea
                        placeholder="-----BEGIN RSA PRIVATE KEY-----"
                        value={formData.privateKey}
                        onChange={(e) => setFormData({ ...formData, privateKey: e.target.value })}
                        className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500 min-h-[80px] font-mono text-xs"
                      />
                      <input
                        type="password"
                        placeholder="私钥密码（可选）"
                        value={formData.passphrase}
                        onChange={(e) => setFormData({ ...formData, passphrase: e.target.value })}
                        className="w-full px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Lock size={16} className="text-[var(--c-600)]" />
                      <input
                        type="password"
                        placeholder="密码（可选）"
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="flex-1 px-3 py-2 bg-[var(--c-950)] border border-[var(--c-800)] rounded-lg text-sm text-[var(--c-200)] placeholder:text-[var(--c-600)] focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] rounded-lg text-sm font-medium transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleSaveForm}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                  <Save size={16} />
                  保存
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 连接列表 */}
      <div className="space-y-6">
        {Object.entries(groupedConnections).map(([group, conns]) => (
          <div key={group}>
            <h3 className="text-xs font-semibold text-[var(--c-600)] uppercase tracking-wider mb-3">{group}</h3>
            <div className="grid grid-cols-2 gap-3">
              {conns.map((conn) => (
                <motion.div
                  key={conn.id}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => handleOpenTerminal(conn)}
                  className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-4 cursor-pointer hover:border-[var(--c-700)] transition-colors group"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Server size={18} className="text-blue-500" />
                      <h4 className="text-sm font-semibold text-[var(--c-200)]">{conn.name}</h4>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => handleEditConnection(conn, e)}
                        className="p-1 hover:bg-[var(--c-800)] rounded text-[var(--c-500)] hover:text-[var(--c-200)]"
                        title="编辑"
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        onClick={(e) => handleCopyConnection(conn, e)}
                        className="p-1 hover:bg-[var(--c-800)] rounded text-[var(--c-500)] hover:text-[var(--c-200)]"
                        title="复制"
                      >
                        <Copy size={14} />
                      </button>
                      <button
                        onClick={(e) => handleDeleteConnection(conn, e)}
                        className="p-1 hover:bg-[var(--c-800)] rounded text-[var(--c-500)] hover:text-red-400"
                        title="删除"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <p className="text-xs text-[var(--c-500)] mb-2">
                    {conn.username}@{conn.host}:{conn.port}
                  </p>
                  <div className="flex items-center gap-2">
                    {conn.tags?.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 bg-[var(--c-950)] text-[10px] text-[var(--c-600)] rounded"
                      >
                        {tag}
                      </span>
                    ))}
                    {conn.lastConnected && (
                      <span className="ml-auto text-[10px] text-[var(--c-600)]">
                        上次连接: {conn.lastConnected}
                      </span>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        ))}

        {connections.length === 0 && (
          <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl p-12 text-center">
            <TerminalIcon size={48} className="mx-auto text-[var(--c-700)] mb-4" />
            <p className="text-[var(--c-500)] mb-4">暂无 SSH 连接</p>
            <button
              onClick={handleNewConnection}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors inline-flex items-center gap-2"
            >
              <Plus size={16} />
              新建连接
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SSHView;
