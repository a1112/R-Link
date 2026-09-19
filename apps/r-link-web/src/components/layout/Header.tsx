import { Settings, FileText } from 'lucide-react';

export interface HeaderProps {
  title: string;
  onOpenSettings: () => void;
  onOpenTerms: () => void;
}

export function Header({ title, onOpenSettings, onOpenTerms }: HeaderProps) {
  return <header className="h-12 border-b border-[var(--c-800)] bg-[var(--c-950)] flex items-center justify-between px-4 shrink-0 select-none" data-tauri-drag-region>
    <h2 className="text-sm font-semibold text-[var(--c-200)]">{title}</h2>
    <div className="flex items-center gap-3">
      <button onClick={onOpenTerms} aria-label="使用条款与隐私" className="p-2 text-[var(--c-500)] hover:text-[var(--c-200)]"><FileText size={18} /></button>
      <button onClick={onOpenSettings} className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--c-300)] hover:bg-[var(--c-800)] rounded-lg"><Settings size={18} />系统设置</button>
    </div>
  </header>;
}

export default Header;
