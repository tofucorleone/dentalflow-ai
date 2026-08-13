import { PageHeader } from "@/components/page-header";
import { PractitionerCardActions } from "@/components/practitioner-card-actions";
import { PractitionerCreateForm } from "@/components/practitioner-create-form";
import { getPractitioners } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function PractitionersPage() {
  const items = await getPractitioners();

  return (
    <>
      <div className="practitioners-page-heading">
        <PageHeader
          title="Praticiens"
          description="Équipe médicale et calendriers associés."
        />

        <PractitionerCreateForm />
      </div>

      <section className="card-grid">
        {items.map((practitioner) => (
          <article
            className="person-card practitioner-admin-card"
            key={practitioner.id}
          >
            <div className="practitioner-card-profile">
              <div className="avatar doctor">Dr</div>

              <div className="practitioner-card-details">
                <div className="practitioner-card-title">
                  <strong>{practitioner.full_name}</strong>

                  <span
                    className={`badge ${
                      practitioner.active
                        ? "success"
                        : "neutral"
                    }`}
                  >
                    {practitioner.active
                      ? "Actif"
                      : "Inactif"}
                  </span>
                </div>

                <p>
                  {practitioner.speciality ?? "Dentiste"}
                </p>

                <span>
                  {practitioner.google_calendar_id
                    ? "Google Calendar connecté"
                    : "Calendrier non configuré"}
                </span>

                {practitioner.phone ? (
                  <span>{practitioner.phone}</span>
                ) : null}

                {practitioner.email ? (
                  <span>{practitioner.email}</span>
                ) : null}
              </div>
            </div>

            <PractitionerCardActions
              practitioner={practitioner}
            />
          </article>
        ))}

        {items.length === 0 ? (
          <article className="panel">
            <p>Aucun praticien enregistré.</p>
          </article>
        ) : null}
      </section>
    </>
  );
}
