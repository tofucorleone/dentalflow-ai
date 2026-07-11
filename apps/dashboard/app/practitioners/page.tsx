import { PageHeader } from "@/components/page-header";
import { getPractitioners } from "@/lib/api";
export default async function Page(){const items=await getPractitioners();return <><PageHeader title="Praticiens" description="Équipe médicale et calendriers associés."/><section className="card-grid">{items.map(p=><article className="person-card" key={p.id}><div className="avatar doctor">Dr</div><div><strong>{p.full_name}</strong><p>{p.speciality??"Dentiste"}</p><span>{p.google_calendar_id?"Google Calendar connecté":"Calendrier non configuré"}</span></div></article>)}</section></>}
