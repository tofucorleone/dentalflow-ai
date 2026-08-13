import Link from "next/link";
import {
  Bot,
  CalendarDays,
  LayoutDashboard,
  MessageCircle,
  Settings,
  Stethoscope,
  UserRound,
  Users,
} from "lucide-react";

import { LogoutButton } from "@/components/logout-button";
import { getClinicBranding } from "@/lib/server-api";

const links = [
  {
    href: "/",
    label: "Tableau de bord",
    icon: LayoutDashboard,
  },
  {
    href: "/copilot",
    label: "Copilote",
    icon: Bot,
  },
  {
    href: "/conversations",
    label: "Conversations",
    icon: MessageCircle,
  },
  {
    href: "/appointments",
    label: "Rendez-vous",
    icon: CalendarDays,
  },
  {
    href: "/patients",
    label: "Patients",
    icon: Users,
  },
  {
    href: "/treatments",
    label: "Soins",
    icon: Stethoscope,
  },
  {
    href: "/practitioners",
    label: "Praticiens",
    icon: UserRound,
  },
  {
    href: "/settings",
    label: "Paramètres",
    icon: Settings,
  },
];

export async function TopNavigation() {
  const branding = await getClinicBranding();

  const softwareInitial = (
    branding.software_name.trim().charAt(0) || "D"
  ).toUpperCase();

  return (
    <header className="top-navigation">
      <div className="top-navigation-inner">
        <Link className="top-brand" href="/">
          <div className="top-brand-mark">
            {branding.logo_url ? (
              <img
                src="/api/clinic-branding/logo"
                alt={`Logo ${branding.display_name}`}
              />
            ) : (
              softwareInitial
            )}
          </div>

          <div className="top-brand-text">
            <strong>{branding.software_name}</strong>
            <span>{branding.display_name}</span>
          </div>
        </Link>

        <nav className="top-nav-links" aria-label="Navigation principale">
          {links.map(({ href, label, icon: Icon }) => (
            <Link className="top-nav-link" href={href} key={href}>
              <Icon size={17} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        <div className="top-nav-actions">
          <LogoutButton />
        </div>
      </div>
    </header>
  );
}
