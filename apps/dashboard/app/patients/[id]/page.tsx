import { notFound } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { PatientNoteForm } from "@/components/patient-note-form";
import { getPatient360 } from "@/lib/patient360";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const fmt = new Intl.DateTimeFormat("fr-DZ", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Africa/Algiers",
});

export default async function PatientPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let data;
  try {
    data = await getPatient360(id);
  } catch {
    notFound();
  }

  return (
    <>
      <PageHeader
        title={data.patient.full_name ?? "Patient"}
        description="Fiche Patient 360° : historique, notes, mémoire IA et communications."
      />

      <section className="patient-profile-grid">
        <article className="panel">
          <div className="patient-hero">
            <div className="avatar patient-large">{(data.patient.full_name ?? "P").slice(0,1).toUpperCase()}</div>
            <div>
              <h2>{data.patient.full_name ?? "Patient sans nom"}</h2>
              <p>{data.patient.phone}</p>
              <span>{data.patient.email ?? "Aucun e-mail"}</span>
            </div>
          </div>
          <div className="patient-kpis">
            <div><strong>{data.appointments.length}</strong><span>Rendez-vous</span></div>
            <div><strong>{data.notes.length}</strong><span>Notes</span></div>
            <div><strong>{data.documents.length}</strong><span>Documents</span></div>
          </div>
        </article>

        <article className="panel">
          <p className="eyebrow">Mémoire IA</p>
          <h2>Résumé patient</h2>
          <p className="patient-memory">
            {data.memory?.summary ?? "Aucun résumé IA enregistré pour ce patient."}
          </p>
          <div className="memory-meta">
            Dernier objectif : {data.memory?.last_goal ?? "Non renseigné"}
          </div>
        </article>
      </section>

      <section className="patient-two-columns">
        <article className="panel">
          <p className="eyebrow">Historique</p>
          <h2>Rendez-vous</h2>
          <div className="timeline-list">
            {data.appointments.map((a) => (
              <div className="timeline-item" key={a.id}>
                <div>
                  <strong>{a.treatment_name ?? "Consultation"}</strong>
                  <span>{a.practitioner_name ?? "Praticien"} · {a.status}</span>
                </div>
                <time>{fmt.format(new Date(a.start_at))}</time>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <p className="eyebrow">Équipe</p>
          <h2>Notes administratives</h2>
          <PatientNoteForm patientId={id} />
          <div className="notes-list">
            {data.notes.map((n) => (
              <article className="note-card" key={n.id}>
                <strong>{n.author_name ?? "Équipe clinique"}</strong>
                <p>{n.note}</p>
                <time>{fmt.format(new Date(n.created_at))}</time>
              </article>
            ))}
          </div>
        </article>
      </section>

      <section className="patient-two-columns">
        <article className="panel">
          <p className="eyebrow">Communications</p>
          <h2>Conversations récentes</h2>
          <div className="conversation-list">
            {data.conversations.length === 0 ? (
              <p className="empty-state">Aucune conversation enregistrée.</p>
            ) : data.conversations.slice(0,20).map((c) => (
              <article className="conversation-item" key={c.id}>
                <div><strong>{c.channel}</strong><span>{c.direction}</span></div>
                <p>{c.message}</p>
                <time>{fmt.format(new Date(c.created_at))}</time>
              </article>
            ))}
          </div>
        </article>

        <article className="panel">
          <p className="eyebrow">Documents</p>
          <h2>Dossier administratif</h2>
          {data.documents.length === 0 ? (
            <p className="empty-state">Aucun document enregistré.</p>
          ) : (
            <div className="document-list">
              {data.documents.map((d) => (
                <a href={d.storage_url} key={d.id} target="_blank" rel="noreferrer">
                  <strong>{d.filename}</strong><span>{d.document_type}</span>
                </a>
              ))}
            </div>
          )}
        </article>
      </section>
    </>
  );
}
