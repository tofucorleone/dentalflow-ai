import Link from "next/link";
import {
  CalendarDays,
  LayoutDashboard,
  Stethoscope,
  Users,
  UserRound,
} from "lucide-react";

import { LogoutButton } from "@/components/logout-button";

const links = [
  { href: "/", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/appointments", label: "Rendez-vous", icon: CalendarDays },
  { href: "/patients", label: "Patients", icon: Users },
  { href: "/treatments", label: "Soins", icon: Stethoscope },
  { href: "/practitioners", label: "Praticiens", icon: UserRound },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">D</div>

        <div>
          <strong>DentalFlow AI</strong>
          <span>Clinique Démo</span>
        </div>
      </div>

      <nav>
        {links.map(({ href, label, icon: Icon }) => (
          <Link className="nav-link" href={href} key={href}>
            <Icon size={19} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot" />
        API et calendrier connectés
      </div>

      <LogoutButton />
    </aside>
  );
}
