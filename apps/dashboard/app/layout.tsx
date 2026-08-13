import type { Metadata } from "next";
import { TopNavigation } from "@/components/top-navigation";
import { getClinicBranding } from "@/lib/server-api";
import "./globals.css";
export const dynamic = "force-dynamic";
export const revalidate = 0;


export const metadata: Metadata = { title: "DentalFlow AI", description: "Gestion de clinique dentaire" };

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const branding = await getClinicBranding();

  return (
    <html lang="fr">
      <body
        style={
          {
            "--primary": branding.primary_color,
            "--clinic-background-image":
              branding.background_image_url
                ? 'url("/api/clinic-branding/background")'
                : "none",
          } as React.CSSProperties
        }
      >
        <div className="app-background" aria-hidden="true" />
        <div className="app-overlay" aria-hidden="true" />

        <div className="app-shell">
          <TopNavigation />
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
