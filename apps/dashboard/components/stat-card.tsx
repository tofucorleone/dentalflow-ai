import type { LucideIcon } from "lucide-react";
export function StatCard({ label, value, detail, icon: Icon }: { label: string; value: string | number; detail: string; icon: LucideIcon }) {
  return <article className="stat-card"><div className="stat-icon"><Icon size={20}/></div><p>{label}</p><strong>{value}</strong><span>{detail}</span></article>;
}
