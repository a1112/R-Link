import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { QrCode, Smartphone, Mail, ArrowRight, Github, Check, X, Loader2, Eye, EyeOff } from "lucide-react";
import { createClient } from "@supabase/supabase-js";
import { projectId, publicAnonKey } from "../utils/supabase/info";

// Initialize Supabase client
const supabaseUrl = `https://${projectId}.supabase.co`;
const supabaseKey = publicAnonKey;
const supabase = createClient(supabaseUrl, supabaseKey);

// Custom Icons for Social Login
const WeChatIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
    <path d="M8.69 14.3c-4.48 0-8.12-3.2-8.12-7.15C.57 3.2 4.21 0 8.69 0c4.48 0 8.12 3.2 8.12 7.15 0 3.94-3.64 7.15-8.12 7.15-.55 0-1.07-.05-1.58-.15L4.4 16l.89-2.61c-2.73-1.64-4.72-4.14-4.72-7.24 0-.05 0-.1.01-.15C.58 5.96 4.22 9.1 8.69 9.1c4.48 0 8.12-3.14 8.12-7.03 0-.05 0-.1-.01-.15.48 3.9-3.16 7.03-7.64 7.03-.55 0-1.07-.05-1.58-.15l.02.03c.51.1.98.24 1.41.42l-.32-1.08zm10.97-1.78c-3.52 0-6.38 2.37-6.38 5.3 0 2.92 2.86 5.3 6.38 5.3.43 0 .84-.04 1.24-.12l2.09 1.15-.7-2.05c1.78-1.22 2.95-3.07 2.95-5.13 0-2.92-2.86-5.3-6.38-5.3-.39.01-.77.03-1.15.08-.02-.01-.03-.02-.05-.03zm-1.88 4.09c.47 0 .85-.34.85-.76 0-.42-.38-.76-.85-.76-.47 0-.85.34-.85.76 0 .42.38.76.85.76zm3.76 0c.47 0 .85-.34.85-.76 0-.42-.38-.76-.85-.76-.47 0-.85.34-.85.76 0 .42.38.76.85.76z" />
  </svg>
);

const QQIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
    <path d="M12.003 2c-5.523 0-10 4.477-10 10 0 5.522 4.477 10 10 10 5.522 0 10-4.478 10-10 0-5.523-4.478-10-10-10zm0 2.219c3.056 0 5.65 1.637 7.062 4.094.275 1.056.294 2.169.056 3.25-.194.887-.562 1.706-1.062 2.438.256.7.406 1.462.406 2.269 0 3.093-2.206 5.644-5.094 6.137v-1.612c1.719-.681 2.938-2.35 2.938-4.306 0-1.775-.988-3.325-2.463-4.119l.55-2.738c-1.356-.881-3.006-1.412-4.781-1.412-1.781 0-3.431.531-4.788 1.412l.55 2.738c-1.475.794-2.462 2.344-2.462 4.119 0 1.956 1.219 3.625 2.938 4.306v1.612c-2.888-.494-5.094-3.044-5.094-6.137 0-.806.15-1.569.406-2.269-.5-.731-.869-1.55-1.062-2.438-.237-1.081-.219-2.194.056-3.25 1.412-2.456 4.006-4.094 7.062-4.094z"/>
  </svg>
);

const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" className="w-5 h-5">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
  </svg>
);

export const AuthPage = ({ onLogin }: { onLogin: (session: any) => void }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [loginMethod, setLoginMethod] = useState<"account" | "scan">("account");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isLogin) {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        if (data.session) onLogin(data.session);
      } else {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        // Auto login after signup if session exists, else tell user to check email
        if (data.session) {
           onLogin(data.session);
        } else {
           setError("请检查您的邮箱完成验证。"); // Should be a success message but handling as text
        }
      }
    } catch (err: any) {
      setError(err.message || "认证失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = async (provider: 'google' | 'github') => {
      // Prompt for real implementation
      try {
          const { data, error } = await supabase.auth.signInWithOAuth({
            provider: provider,
          });
          if (error) throw error;
      } catch (err: any) {
          setError("社交登录配置未启用");
      }
  };

  return (
    <div className="flex items-center justify-center min-h-full w-full p-4 relative overflow-hidden">
      {/* Dynamic Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
         <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-blue-500/20 rounded-full blur-[120px] animate-pulse" />
         <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-purple-500/20 rounded-full blur-[120px] animate-pulse" style={{ animationDelay: "2s" }} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-md bg-[var(--c-950-80)] backdrop-blur-2xl border border-[var(--c-800)] rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="p-8 pb-0 text-center">
            <div className="w-12 h-12 bg-[var(--c-100)] rounded-xl flex items-center justify-center text-[var(--c-950)] mx-auto mb-4 shadow-lg shadow-[var(--c-100)]/20">
                <Smartphone size={24} strokeWidth={2.5} />
            </div>
            <h1 className="text-2xl font-bold text-[var(--c-100)] tracking-tight mb-2">
                {isLogin ? "欢迎回来" : "创建账户"}
            </h1>
            <p className="text-[var(--c-500)] text-sm">
                R-Link 基础互联平台
            </p>
        </div>

        {/* Tabs for Login Method (Only show in Login mode) */}
        {isLogin && (
            <div className="flex items-center justify-center gap-6 mt-6 border-b border-[var(--c-800-50)] px-8">
                <button
                    onClick={() => setLoginMethod("account")}
                    className={`pb-3 text-sm font-medium transition-all relative ${
                        loginMethod === "account" ? "text-[var(--c-100)]" : "text-[var(--c-500)] hover:text-[var(--c-300)]"
                    }`}
                >
                    账号登录
                    {loginMethod === "account" && (
                        <motion.div layoutId="auth-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--c-100)] rounded-full" />
                    )}
                </button>
                <button
                    onClick={() => setLoginMethod("scan")}
                    className={`pb-3 text-sm font-medium transition-all relative ${
                        loginMethod === "scan" ? "text-[var(--c-100)]" : "text-[var(--c-500)] hover:text-[var(--c-300)]"
                    }`}
                >
                    扫码登录
                    {loginMethod === "scan" && (
                        <motion.div layoutId="auth-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--c-100)] rounded-full" />
                    )}
                </button>
            </div>
        )}

        <div className="p-8 pt-6">
            <AnimatePresence mode="wait">
                {loginMethod === "scan" && isLogin ? (
                    <motion.div
                        key="scan"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="flex flex-col items-center justify-center py-4 space-y-6"
                    >
                         <div className="relative group cursor-pointer">
                             <div className="w-48 h-48 bg-white p-2 rounded-xl shadow-inner flex items-center justify-center overflow-hidden relative">
                                  {/* Mock QR Code */}
                                  <div className="absolute inset-0 bg-white z-0"></div>
                                  <div className="z-10 w-full h-full opacity-90" style={{
                                      backgroundImage: `url("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=r-link-login-token")`,
                                      backgroundSize: 'cover'
                                  }}></div>
                                  
                                  {/* Scan Overlay Animation */}
                                  <motion.div 
                                    className="absolute top-0 left-0 w-full h-1 bg-blue-500/50 shadow-[0_0_15px_rgba(59,130,246,0.5)] z-20"
                                    animate={{ top: ["0%", "100%", "0%"] }}
                                    transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                                  />
                             </div>
                             <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 rounded-xl backdrop-blur-sm z-30">
                                 <p className="text-white font-medium text-sm">点击刷新二维码</p>
                             </div>
                         </div>
                         <div className="text-center space-y-1">
                             <p className="text-sm text-[var(--c-200)] font-medium">请使用 微信 或 QQ 扫码登录</p>
                             <p className="text-xs text-[var(--c-500)]">支持 R-Link 移动端 App 扫码</p>
                         </div>
                    </motion.div>
                ) : (
                    <motion.div
                        key="form"
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        className="space-y-5"
                    >
                         <form onSubmit={handleAuth} className="space-y-4">
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-[var(--c-400)] ml-1">电子邮箱</label>
                                <div className="relative group">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--c-500)] group-focus-within:text-[var(--c-200)] transition-colors" size={18} />
                                    <input
                                        type="email"
                                        required
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="user@example.com"
                                        className="w-full bg-[var(--c-900)] border border-[var(--c-800)] text-[var(--c-100)] text-sm rounded-xl py-2.5 pl-10 pr-4 outline-none focus:border-[var(--c-500)] focus:ring-1 focus:ring-[var(--c-500)] transition-all placeholder:text-[var(--c-600)]"
                                    />
                                </div>
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-[var(--c-400)] ml-1">密码</label>
                                <div className="relative group">
                                    <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--c-500)] group-focus-within:text-[var(--c-200)] transition-colors">
                                        <div className="text-[10px] font-mono tracking-widest">***</div>
                                    </div>
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        required
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="••••••••"
                                        className="w-full bg-[var(--c-900)] border border-[var(--c-800)] text-[var(--c-100)] text-sm rounded-xl py-2.5 pl-10 pr-10 outline-none focus:border-[var(--c-500)] focus:ring-1 focus:ring-[var(--c-500)] transition-all placeholder:text-[var(--c-600)]"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--c-500)] hover:text-[var(--c-300)] transition-colors"
                                    >
                                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            {error && (
                                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
                                    <AlertCircle size={14} className="shrink-0" />
                                    {error}
                                </div>
                            )}

                            <div className="flex items-center justify-between text-xs">
                                <label className="flex items-center gap-2 cursor-pointer group">
                                    <div className="w-3.5 h-3.5 rounded border border-[var(--c-700)] bg-[var(--c-900)] flex items-center justify-center group-hover:border-[var(--c-500)] transition-colors">
                                        {/* Checkbox state simulation */}
                                        {/* <Check size={10} className="text-[var(--c-100)]" /> */}
                                    </div>
                                    <span className="text-[var(--c-500)] group-hover:text-[var(--c-300)] transition-colors">记住我</span>
                                </label>
                                <button type="button" className="text-[var(--c-400)] hover:text-[var(--c-200)] transition-colors">忘记密码?</button>
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full bg-[var(--c-100)] text-[var(--c-950)] font-medium py-2.5 rounded-xl hover:bg-[var(--c-white)] active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
                            >
                                {loading && <Loader2 size={16} className="animate-spin" />}
                                {isLogin ? "登 录" : "注册账户"}
                            </button>
                         </form>

                         <div className="relative">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-[var(--c-800)]"></div>
                            </div>
                            <div className="relative flex justify-center text-xs uppercase">
                                <span className="bg-[var(--c-900)] px-2 text-[var(--c-500)] rounded">或继续使用</span>
                            </div>
                         </div>

                         <div className="grid grid-cols-3 gap-3">
                             <button onClick={() => setLoginMethod('scan')} className="flex items-center justify-center py-2.5 bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl hover:bg-[#07C160] hover:border-[#07C160] hover:text-white text-[var(--c-400)] transition-all group">
                                 <WeChatIcon />
                             </button>
                             <button onClick={() => setLoginMethod('scan')} className="flex items-center justify-center py-2.5 bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl hover:bg-[#12B7F5] hover:border-[#12B7F5] hover:text-white text-[var(--c-400)] transition-all group">
                                 <QQIcon />
                             </button>
                             <button onClick={() => handleSocialLogin('google')} className="flex items-center justify-center py-2.5 bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl hover:bg-[var(--c-800-50)] hover:text-white text-[var(--c-400)] transition-all">
                                 <GoogleIcon />
                             </button>
                         </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="p-4 bg-[var(--c-900-50)] border-t border-[var(--c-800-50)] text-center">
            <button
                onClick={() => {
                    setIsLogin(!isLogin);
                    setLoginMethod('account');
                    setError(null);
                }}
                className="text-sm text-[var(--c-500)] hover:text-[var(--c-200)] transition-colors flex items-center justify-center gap-1 mx-auto"
            >
                {isLogin ? "还没有账户? 立即注册" : "已有账户? 直接登录"}
                <ArrowRight size={14} />
            </button>
        </div>
      </motion.div>

      {/* Footer Info */}
      <div className="absolute bottom-6 text-xs text-[var(--c-600)]">
         &copy; 2026 R-Link Network. By logging in, you agree to our Terms & Privacy Policy.
      </div>
    </div>
  );
};
