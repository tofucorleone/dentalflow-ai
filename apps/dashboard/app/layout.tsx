import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";
export const dynamic = "force-dynamic";
export const revalidate = 0;


export const metadata: Metadata = { title: "DentalFlow AI", description: "Gestion de clinique dentaire" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fr"><body><div className="app-shell"><Sidebar/><main className="content">{children}</main></div></body></html>;
}
