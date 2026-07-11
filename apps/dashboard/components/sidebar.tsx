import Link from "next/link";
import { CalendarDays, LayoutDashboard, Stethoscope, Users, UserRound } from "lucide-react";

const items = [
  ["/", "Tableau de bord", LayoutDashboard],
  ["/appointments", "Rendez-vous", CalendarDays],
  ["/patients", "Patients", Users],
  ["/treatments", "Soins", Stethoscope],
  ["/practitioners", "Praticiens", UserRound],
] as const;

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">D</div><div><strong>DentalFlow AI</strong><span>Clinique Démo</span></div></div>
      <nav>{items.map(([href, label, Icon]) => <Link className="nav-link" href={href} key={href}><Icon size={19}/><span>{label}</span></Link>)}</nav>
      <div className="sidebar-footer"><span className="status-dot"/>API et calendrier connectés</div>
    </aside>
  );
}
