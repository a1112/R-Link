/**
 * 认证页面组件
 * 包含登录和注册功能
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Command,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  User,
  QrCode,
  MessageCircle,
  MessageSquare,
  Chrome,
  Github,
  Twitter,
} from "lucide-react";
import { toast } from "sonner";

export interface AuthScreenProps {
  /** 登录成功回调 */
  onLogin: () => void;
  /** 游客登录回调 */
  onGuestLogin?: () => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({ onLogin, onGuestLogin }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [authMethod, setAuthMethod] = useState<'password' | 'qrcode'>('password');
  const [showPassword, setShowPassword] = useState(false);
  const [agreementChecked, setAgreementChecked] = useState(false);

  const handleLogin = () => {
    if (!agreementChecked) {
      toast.error("请先阅读并同意用户协议");
      return;
    }
    onLogin();
  };

  const handleGuestLogin = () => {
    if (!agreementChecked) {
      toast.error("请先阅读并同意用户协议");
      return;
    }
    toast.success("已开启游客体验模式");
    onGuestLogin?.();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--c-950)] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,var(--c-900),var(--c-950))]">
      {/* Background Decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-blue-500/10 rounded-full blur-[100px]" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-emerald-500/10 rounded-full blur-[100px]" />
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
          }}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md bg-[var(--c-950-50)] backdrop-blur-2xl border border-[var(--c-800-50)] rounded-2xl shadow-2xl relative overflow-hidden flex flex-col"
      >
        {/* Header Section */}
        <div className="p-8 pb-4 text-center relative z-10">
          <div className="absolute top-4 right-4">
            <button
              onClick={handleGuestLogin}
              className="text-xs font-medium text-[var(--c-500)] hover:text-[var(--c-200)] px-3 py-1.5 rounded-full border border-[var(--c-800)] hover:bg-[var(--c-800)] transition-colors flex items-center gap-1"
            >
              <User size={12} /> 游客模式
            </button>
          </div>

          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-[var(--c-800)] text-[var(--c-100)] mb-4 shadow-lg border border-[var(--c-700)]">
            <Command size={24} strokeWidth={3} />
          </div>
          <h2 className="text-2xl font-bold text-[var(--c-100)] tracking-tight mb-1">
            {isLogin ? "欢迎回来" : "创建账户"}
          </h2>
          <p className="text-[var(--c-500)] text-sm">
            {isLogin ? "登录您的 R-Link 控制台" : "开始您的远程互联之旅"}
          </p>
        </div>

        {/* Content */}
        <motion.div layout className="p-8 pt-2 flex-1 relative z-10">
          {/* Tabs for Login Type */}
          {isLogin && (
            <div className="flex p-1 bg-[var(--c-900)] rounded-lg mb-6 border border-[var(--c-800)]">
              <button
                onClick={() => setAuthMethod('password')}
                className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-medium rounded-md transition-all ${
                  authMethod === 'password'
                    ? "bg-[var(--c-800)] text-[var(--c-100)] shadow-sm"
                    : "text-[var(--c-500)] hover:text-[var(--c-300)]"
                }`}
              >
                <Lock size={14} /> 账号密码
              </button>
              <button
                onClick={() => setAuthMethod('qrcode')}
                className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-medium rounded-md transition-all ${
                  authMethod === 'qrcode'
                    ? "bg-[var(--c-800)] text-[var(--c-100)] shadow-sm"
                    : "text-[var(--c-500)] hover:text-[var(--c-300)]"
                }`}
              >
                <QrCode size={14} /> 扫码登录
              </button>
            </div>
          )}

          <AnimatePresence mode="wait">
            {authMethod === 'password' ? (
              <motion.div
                key="password-form"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="space-y-4"
              >
                <div className="space-y-2">
                  <label className="text-xs font-medium text-[var(--c-400)] ml-1">电子邮箱</label>
                  <div className="relative group">
                    <Mail className="absolute left-3 top-2.5 text-[var(--c-600)] group-focus-within:text-[var(--c-300)] transition-colors" size={16} />
                    <input
                      type="email"
                      placeholder="name@example.com"
                      className="w-full bg-[var(--c-900-50)] border border-[var(--c-800)] text-[var(--c-200)] text-sm rounded-lg pl-10 pr-4 py-2.5 outline-none focus:border-[var(--c-600)] focus:ring-1 focus:ring-[var(--c-600)] transition-all placeholder:text-[var(--c-700)]"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center ml-1">
                    <label className="text-xs font-medium text-[var(--c-400)]">密码</label>
                    {isLogin && <button className="text-xs text-[var(--c-500)] hover:text-[var(--c-300)] transition-colors">忘记密码?</button>}
                  </div>
                  <div className="relative group">
                    <Lock className="absolute left-3 top-2.5 text-[var(--c-600)] group-focus-within:text-[var(--c-300)] transition-colors" size={16} />
                    <input
                      type={showPassword ? "text" : "password"}
                      placeholder="••••••••"
                      className="w-full bg-[var(--c-900-50)] border border-[var(--c-800)] text-[var(--c-200)] text-sm rounded-lg pl-10 pr-10 py-2.5 outline-none focus:border-[var(--c-600)] focus:ring-1 focus:ring-[var(--c-600)] transition-all placeholder:text-[var(--c-700)]"
                    />
                    <button
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-2.5 text-[var(--c-600)] hover:text-[var(--c-300)] focus:outline-none"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div className="flex items-start gap-2 py-1">
                  <div className="relative flex items-center h-4 mt-0.5">
                    <input
                      id="agreement"
                      type="checkbox"
                      checked={agreementChecked}
                      onChange={(e) => setAgreementChecked(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 text-blue-600 focus:ring-blue-600 bg-[var(--c-900)]"
                    />
                  </div>
                  <label htmlFor="agreement" className="text-xs text-[var(--c-500)] leading-tight select-none cursor-pointer">
                    我已阅读并同意 <span className="text-blue-400 hover:underline">用户协议</span> 与 <span className="text-blue-400 hover:underline">隐私政策</span>
                  </label>
                </div>

                <button
                  onClick={handleLogin}
                  className="w-full bg-[var(--c-100)] hover:bg-[var(--c-white)] text-[var(--c-950)] font-semibold py-2.5 rounded-lg transition-all transform active:scale-[0.98] shadow-lg shadow-white/5 mt-2 flex items-center justify-center gap-2"
                >
                  {isLogin ? "登录" : "注册"} <ArrowRight size={16} />
                </button>
              </motion.div>
            ) : (
              <motion.div
                key="qrcode-view"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="flex flex-col items-center justify-center py-4 space-y-4"
              >
                <div className="w-48 h-48 bg-white rounded-xl p-2 shadow-inner flex items-center justify-center">
                  {/* Mock QR Code */}
                  <div className="w-full h-full border-4 border-[var(--c-900)] border-dashed opacity-10" />
                  <QrCode size={120} className="text-zinc-900 absolute" />
                </div>
                <p className="text-xs text-[var(--c-500)] text-center">
                  请使用 微信 或 QQ 扫描二维码<br/>安全登录 R-Link
                </p>
                <div className="flex items-center gap-2 mt-2">
                  <input
                    id="agreement-qr"
                    type="checkbox"
                    checked={agreementChecked}
                    onChange={(e) => setAgreementChecked(e.target.checked)}
                    className="w-3 h-3 rounded border-gray-600 text-blue-600 bg-[var(--c-900)]"
                  />
                  <label htmlFor="agreement-qr" className="text-xs text-[var(--c-500)] select-none cursor-pointer">
                    已阅读并同意用户协议
                  </label>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[var(--c-800)]"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-2 bg-[var(--c-950)] text-[var(--c-600)]">第三方登录</span>
            </div>
          </div>

          <div className="grid grid-cols-5 gap-3">
            <button className="flex items-center justify-center py-2.5 border border-[var(--c-800)] rounded-lg hover:bg-[var(--c-800-50)] transition-colors group">
              <MessageCircle size={20} className="text-emerald-500 group-hover:scale-110 transition-transform" />
            </button>
            <button className="flex items-center justify-center py-2.5 border border-[var(--c-800)] rounded-lg hover:bg-[var(--c-800-50)] transition-colors group">
              <MessageSquare size={20} className="text-blue-500 group-hover:scale-110 transition-transform" fill="currentColor" fillOpacity={0.2} />
            </button>
            <button className="flex items-center justify-center py-2.5 border border-[var(--c-800)] rounded-lg hover:bg-[var(--c-800-50)] transition-colors group">
              <Chrome size={20} className="text-[var(--c-200)] group-hover:scale-110 transition-transform" />
            </button>
            <button className="flex items-center justify-center py-2.5 border border-[var(--c-800)] rounded-lg hover:bg-[var(--c-800-50)] transition-colors group">
              <Github size={20} className="text-[var(--c-200)] group-hover:scale-110 transition-transform" />
            </button>
            <button className="flex items-center justify-center py-2.5 border border-[var(--c-800)] rounded-lg hover:bg-[var(--c-800-50)] transition-colors group">
              <Twitter size={20} className="text-sky-400 group-hover:scale-110 transition-transform" />
            </button>
          </div>
        </motion.div>

        {/* Footer */}
        <div className="p-4 bg-[var(--c-900-50)] border-t border-[var(--c-800-50)] text-center">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-xs text-[var(--c-400)] hover:text-[var(--c-200)] transition-colors"
          >
            {isLogin ? (
              <>还没有账号? <span className="text-blue-400 font-medium">立即注册</span></>
            ) : (
              <>已有账号? <span className="text-blue-400 font-medium">直接登录</span></>
            )}
          </button>
        </div>
      </motion.div>
    </div>
  );
};

export default AuthScreen;
