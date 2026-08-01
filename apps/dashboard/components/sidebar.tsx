import Link from "next/link";
import {
  CalendarDays,
  LayoutDashboard,
  Stethoscope,
  Users,
  UserRound,
  Settings,
} from "lucide-react";

import { LogoutButton } from "@/components/logout-button";
import { getClinicBranding } from "@/lib/server-api";

const links = [
  { href: "/", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/appointments", label: "Rendez-vous", icon: CalendarDays },
  { href: "/patients", label: "Patients", icon: Users },
  { href: "/treatments", label: "Soins", icon: Stethoscope },
  { href: "/practitioners", label: "Praticiens", icon: UserRound },
  { href: "/settings", label: "Paramètres", icon: Settings },
];

export async function Sidebar() {
  const branding = await getClinicBranding();
  const softwareInitial = (
    branding.software_name.trim().charAt(0) || "D"
  ).toUpperCase();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">{softwareInitial}</div>

        <div>
          <strong>{branding.software_name}</strong>
          <span>{branding.display_name}</span>
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
