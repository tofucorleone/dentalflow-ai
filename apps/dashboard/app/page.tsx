import { CalendarCheck, CircleDollarSign, Stethoscope, Users } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { getAppointments, getPatients, getPractitioners, getTreatments } from "@/lib/api";

export default async function DashboardPage() {
  const [appointments, patients, treatments, practitioners] = await Promise.all([
    getAppointments(), getPatients(), getTreatments(), getPractitioners()
  ]);
  const confirmed = appointments.filter(a => a.status === "confirmed");
  const revenue = confirmed.reduce((sum, a) => sum + Number(treatments.find(t => t.name === a.treatment_name)?.price ?? 0), 0);
  return <>
    <PageHeader title="Vue d’ensemble" description="Activité de la clinique, patients et rendez-vous."/>
    <section className="stats-grid">
      <StatCard label="Rendez-vous confirmés" value={confirmed.length} detail="Tous les rendez-vous actifs" icon={CalendarCheck}/>
      <StatCard label="Patients" value={patients.length} detail="Patients enregistrés" icon={Users}/>
      <StatCard label="Soins actifs" value={treatments.length} detail="Catalogue configurable" icon={Stethoscope}/>
      <StatCard label="CA prévisionnel" value={`${revenue.toLocaleString("fr-DZ")} DA`} detail={`${practitioners.length} praticien(s)`} icon={CircleDollarSign}/>
    </section>
    <section className="panel">
      <div className="panel-heading"><div><p className="eyebrow">Agenda</p><h2>Rendez-vous récents</h2></div><a className="text-link" href="/appointments">Voir tout</a></div>
      <div className="appointment-list">
        {confirmed.slice(0,6).map(a => <article className="appointment-row" key={a.id}>
          <div className="appointment-main"><strong>{a.patient_name ?? "Patient"}</strong><span>{a.treatment_name ?? "Consultation"} · {a.practitioner_name ?? "Praticien"}</span></div>
          <time>{new Intl.DateTimeFormat("fr-DZ",{dateStyle:"medium",timeStyle:"short",timeZone:"Africa/Algiers"}).format(new Date(a.start_at))}</time>
          <span className="badge success">Confirmé</span>
        </article>)}
      </div>
    </section>
  </>;
}
