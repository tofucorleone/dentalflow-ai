import { getClinicBranding } from "@/lib/server-api";

type PageHeaderProps = {
  title: string;
  description: string;
};

export async function PageHeader({
  title,
  description,
}: PageHeaderProps) {
  const branding = await getClinicBranding();

  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{branding.display_name}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>

      <div className="live-pill">
        <span className="status-dot" />
        Synchronisé
      </div>
    </header>
  );
}
