/**
 * 用户协议和隐私条款弹窗组件
 *
 * 用于首次登录时展示用户协议和隐私政策
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileText, Shield, Eye, ChevronRight, Check } from "lucide-react";

export interface TermsModalProps {
  /** 是否显示 */
  show: boolean;
  /** 关闭回调 */
  onClose: () => void;
  /** 同意回调 */
  onAgree: () => void;
  /** 是否强制同意（不允许关闭） */
  forceAgree?: boolean;
  /** 标题 */
  title?: string;
}

type TermsTab = 'terms' | 'privacy';

interface SectionProps {
  title: string;
  children: React.ReactNode;
}

const Section: React.FC<SectionProps> = ({ title, children }) => (
  <div className="mb-6">
    <h4 className="text-sm font-semibold text-[var(--c-100)] mb-2">{title}</h4>
    <div className="text-xs text-[var(--c-400)] leading-relaxed">{children}</div>
  </div>
);

export const TermsModal: React.FC<TermsModalProps> = ({
  show,
  onClose,
  onAgree,
  forceAgree = false,
  title = "使用条款与隐私政策"
}) => {
  const [activeTab, setActiveTab] = useState<TermsTab>('terms');
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [agreedToPrivacy, setAgreedToPrivacy] = useState(false);
  const [scrolledToBottom, setScrolledToBottom] = useState(false);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement;
    const { scrollTop, scrollHeight, clientHeight } = target;
    // 检查是否滚动到底部（允许 5px 的误差）
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 5;
    setScrolledToBottom(isAtBottom);
  };

  const handleAgree = () => {
    if (agreedToTerms && agreedToPrivacy) {
      onAgree();
    }
  };

  const canAgree = agreedToTerms && agreedToPrivacy && scrolledToBottom;

  if (!show) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'var(--c-modal-overlay)' }}
      onClick={forceAgree ? undefined : onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.2 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl bg-[var(--c-950)] border border-[var(--c-800)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
      >
        {/* Header */}
        <div className="shrink-0 px-6 py-4 border-b border-[var(--c-800)] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Shield size={20} className="text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-[var(--c-100)]">{title}</h3>
              <p className="text-xs text-[var(--c-500)]">请仔细阅读并同意以下条款</p>
            </div>
          </div>
          {!forceAgree && (
            <button
              onClick={onClose}
              className="p-2 text-[var(--c-500)] hover:text-[var(--c-200)] hover:bg-[var(--c-800)] rounded-lg transition-colors"
            >
              <X size={18} />
            </button>
          )}
        </div>

        {/* Tabs */}
        <div className="shrink-0 flex border-b border-[var(--c-800)]">
          <button
            onClick={() => setActiveTab('terms')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'terms'
                ? 'text-[var(--c-100)]'
                : 'text-[var(--c-500)] hover:text-[var(--c-300)]'
            }`}
          >
            <FileText size={16} />
            用户协议
            {activeTab === 'terms' && (
              <motion.div
                layoutId="activeTab"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"
                initial={false}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            )}
          </button>
          <button
            onClick={() => setActiveTab('privacy')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'privacy'
                ? 'text-[var(--c-100)]'
                : 'text-[var(--c-500)] hover:text-[var(--c-300)]'
            }`}
          >
            <Eye size={16} />
            隐私政策
            {activeTab === 'privacy' && (
              <motion.div
                layoutId="activeTab"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"
                initial={false}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            )}
          </button>
        </div>

        {/* Content */}
        <div
          className="flex-1 overflow-y-auto p-6 scrollbar-card"
          onScroll={handleScroll}
        >
          <AnimatePresence mode="wait">
            {activeTab === 'terms' && (
              <motion.div
                key="terms"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                transition={{ duration: 0.15 }}
                className="space-y-2"
              >
                <Section title="1. 服务条款的接受">
                  欢迎使用 R-Link 平台！通过访问或使用本服务，您确认您已阅读、理解并同意受这些条款和条件的约束。
                  如果您不同意这些条款，请不要使用我们的服务。
                </Section>

                <Section title="2. 服务描述">
                  R-Link 是一个插件化管理平台，提供远程连接、文件管理、插件系统等功能。
                  我们保留随时修改、暂停或终止服务的权利，恕不另行通知。
                </Section>

                <Section title="3. 用户责任">
                  您同意对您的账户和活动的安全性负责。您不得：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>使用服务进行任何非法目的</li>
                    <li>侵犯他人的知识产权</li>
                    <li>传播恶意软件或病毒</li>
                    <li>滥用或干扰服务的运行</li>
                  </ul>
                </Section>

                <Section title="4. 知识产权">
                  平台的所有内容，包括但不限于文字、图形、标识、图像和软件，
                  均受版权和其他知识产权法的保护。未经明确许可，您不得复制、修改或分发任何内容。
                </Section>

                <Section title="5. 免责声明">
                  服务按"原样"提供，不提供任何明示或暗示的保证。我们不对以下情况承担责任：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>服务中断或错误</li>
                    <li>数据丢失或损坏</li>
                    <li>第三方软件或服务的问题</li>
                  </ul>
                </Section>

                <Section title="6. 条款变更">
                  我们保留随时修改这些条款的权利。变更后继续使用服务即表示您接受修改后的条款。
                  重大变更将通过平台通知或邮件告知。
                </Section>

                <Section title="7. 终止">
                  我们保留在您违反这些条款时暂停或终止您账户访问权限的权利。
                  您也可以随时停止使用服务并删除您的账户。
                </Section>
              </motion.div>
            )}

            {activeTab === 'privacy' && (
              <motion.div
                key="privacy"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.15 }}
                className="space-y-2"
              >
                <Section title="1. 信息收集">
                  我们可能收集以下类型的信息：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li><strong>账户信息：</strong>用户名、邮箱地址</li>
                    <li><strong>使用数据：</strong>登录时间、操作日志</li>
                    <li><strong>设备信息：</strong>IP 地址、浏览器类型、操作系统</li>
                    <li><strong>插件数据：</strong>已安装插件列表和配置</li>
                  </ul>
                </Section>

                <Section title="2. 信息使用">
                  我们使用收集的信息用于：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>提供、维护和改进服务</li>
                    <li>处理交易和发送相关通知</li>
                    <li>发送技术通知、更新和安全警报</li>
                    <li>响应评论、问题和客户服务请求</li>
                    <li>监控和分析使用趋势</li>
                  </ul>
                </Section>

                <Section title="3. 信息共享">
                  我们不会出售、交易或出租您的个人信息。我们可能在以下情况下共享信息：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>获得您的同意</li>
                    <li>遵守法律义务或保护我们的权利</li>
                    <li>与服务提供商合作（如 Supabase）</li>
                  </ul>
                </Section>

                <Section title="4. 数据安全">
                  我们采取合理的技术和组织措施来保护您的数据：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>使用 HTTPS 加密传输</li>
                    <li>密码哈希存储</li>
                    <li>定期安全审计</li>
                    <li>访问控制和身份验证</li>
                  </ul>
                </Section>

                <Section title="5. Cookie 政策">
                  我们使用 Cookie 和类似技术来：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>记住您的登录状态</li>
                    <li>记住您的偏好设置</li>
                    <li>分析平台使用情况</li>
                  </ul>
                  您可以通过浏览器设置管理 Cookie。
                </Section>

                <Section title="6. 您的权利">
                  您对自己的数据拥有以下权利：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li><strong>访问权：</strong>请求查看我们持有的您的数据</li>
                    <li><strong>更正权：</strong>更新或修正不准确的信息</li>
                    <li><strong>删除权：</strong>请求删除您的账户和数据</li>
                    <li><strong>反对权：</strong>反对某些数据处理活动</li>
                  </ul>
                </Section>

                <Section title="7. 数据保留">
                  我们仅在必要期间保留您的数据。当您删除账户时，我们将：
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>立即删除您的个人信息</li>
                    <li>在 30 天内删除相关日志和备份数据</li>
                    <li>保留法律要求必须保留的数据</li>
                  </ul>
                </Section>

                <Section title="8. 儿童隐私">
                  我们的服务不面向 13 岁以下的儿童。如果我们发现收集了此类信息，
                      将立即删除。如果您是家长或监护人，请联系我们。
                </Section>

                <Section title="9. 隐私政策变更">
                  我们可能会更新本隐私政策。重大变更将通过平台通知您。
                  继续使用服务即表示您接受更新的政策。
                </Section>

                <Section title="10. 联系我们">
                  如果您对本隐私政策有任何疑问，请通过以下方式联系我们：
                  <div className="mt-2 p-3 bg-[var(--c-900)] rounded-lg border border-[var(--c-800)]">
                    <div className="text-[var(--c-300)]">
                      <p>邮箱：privacy@r-link.dev</p>
                      <p>GitHub：github.com/r-link/r-link</p>
                    </div>
                  </div>
                </Section>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer - Checkboxes */}
        <div className="shrink-0 px-6 py-4 border-t border-[var(--c-800)] bg-[var(--c-900-30)]">
          <div className="space-y-3 mb-4">
            <label className="flex items-start gap-3 cursor-pointer group">
              <div className="relative mt-0.5">
                <input
                  type="checkbox"
                  checked={agreedToTerms}
                  onChange={(e) => setAgreedToTerms(e.target.checked)}
                  className="peer appearance-none w-5 h-5 border-2 border-[var(--c-700)] rounded bg-[var(--c-900)] checked:bg-blue-500 checked:border-blue-500 transition-colors cursor-pointer"
                />
                <Check size={14} className="absolute top-1 left-1 text-white opacity-0 peer-checked:opacity-100 pointer-events-none transition-opacity" />
              </div>
              <span className={`text-sm ${agreedToTerms ? 'text-[var(--c-200)]' : 'text-[var(--c-400)]'}`}>
                我已阅读并同意<span className="text-[var(--c-100)] font-medium">《用户协议》</span>
              </span>
            </label>

            <label className="flex items-start gap-3 cursor-pointer group">
              <div className="relative mt-0.5">
                <input
                  type="checkbox"
                  checked={agreedToPrivacy}
                  onChange={(e) => setAgreedToPrivacy(e.target.checked)}
                  className="peer appearance-none w-5 h-5 border-2 border-[var(--c-700)] rounded bg-[var(--c-900)] checked:bg-blue-500 checked:border-blue-500 transition-colors cursor-pointer"
                />
                <Check size={14} className="absolute top-1 left-1 text-white opacity-0 peer-checked:opacity-100 pointer-events-none transition-opacity" />
              </div>
              <span className={`text-sm ${agreedToPrivacy ? 'text-[var(--c-200)]' : 'text-[var(--c-400)]'}`}>
                我已阅读并同意<span className="text-[var(--c-100)] font-medium">《隐私政策》</span>
              </span>
            </label>
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
            {!forceAgree && (
              <button
                onClick={onClose}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-[var(--c-400)] hover:text-[var(--c-200)] bg-[var(--c-800)] hover:bg-[var(--c-700)] rounded-xl transition-colors"
              >
                稍后再说
              </button>
            )}
            <button
              onClick={handleAgree}
              disabled={!canAgree}
              className={`flex-1 px-4 py-2.5 text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2 ${
                canAgree
                  ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:shadow-lg hover:shadow-blue-500/25'
                  : 'bg-[var(--c-800)] text-[var(--c-600)] cursor-not-allowed'
              }`}
            >
              {canAgree ? (
                <>
                  <Check size={16} />
                  同意并继续
                </>
              ) : (
                <>
                  请阅读完整内容后同意
                </>
              )}
            </button>
          </div>

          {/* Scroll indicator */}
          {!scrolledToBottom && (
            <div className="mt-3 flex items-center justify-center gap-2 text-xs text-[var(--c-500)]">
              <ChevronRight size={14} className="rotate-90" />
              请向下滚动阅读完整内容
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default TermsModal;
