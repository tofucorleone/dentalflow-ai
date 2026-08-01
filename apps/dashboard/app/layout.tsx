import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
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
          } as React.CSSProperties
        }
      >
        <div className="app-shell">
          <Sidebar />
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
