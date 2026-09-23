import { Wrench } from 'lucide-react';

export function UnavailableFeature({ title, description }: { title: string; description: string }) {
  return <section className="rounded-xl border border-[var(--c-800)] bg-[var(--c-900)] p-8 space-y-4">
    <Wrench size={28} className="text-[var(--c-500)]" />
    <h2 className="text-xl font-semibold">{title}</h2>
    <p role="status" className="text-amber-400">此功能尚未接入</p>
    <p className="text-sm text-[var(--c-400)] leading-relaxed">{description}</p>
  </section>;
}
