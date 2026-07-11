export function PageHeader({ title, description }: { title: string; description: string }) {
  return <header className="page-header"><div><p className="eyebrow">Clinique Dentaire Démo</p><h1>{title}</h1><p>{description}</p></div><div className="live-pill"><span className="status-dot"/>Synchronisé</div></header>;
}
