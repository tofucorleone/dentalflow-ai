import { PageHeader } from "@/components/page-header";
import { TreatmentCardActions } from "@/components/treatment-card-actions";
import { TreatmentCreateForm } from "@/components/treatment-create-form";
import { getTreatments } from "@/lib/api";
import { getClinicBranding } from "@/lib/server-api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function TreatmentsPage() {
  const [items, branding] = await Promise.all([
    getTreatments(),
    getClinicBranding(),
  ]);

  return (
    <>
      <div className="treatments-page-heading">
        <PageHeader
          title="Soins"
          description="Tarifs, durées et prestations."
        />

        <TreatmentCreateForm
          currencyLabel={branding.currency_label}
        />
      </div>

      <section className="card-grid">
        {items.map((treatment) => (
          <article
            className="treatment-card treatment-admin-card"
            key={treatment.id}
          >
            <div className="panel-heading">
              <strong>{treatment.name}</strong>

              <span
                className={`badge ${
                  treatment.active ? "success" : "neutral"
                }`}
              >
                {treatment.active ? "Actif" : "Inactif"}
              </span>
            </div>

            <p>
              {treatment.description ?? "Aucune description"}
            </p>

            <div className="treatment-meta">
              <span>{treatment.duration_minutes} minutes</span>

              <strong>
                {Number(treatment.price).toLocaleString("fr-DZ")}{" "}
                {branding.currency_label}
              </strong>
            </div>

            <TreatmentCardActions
              treatment={treatment}
              currencyLabel={branding.currency_label}
            />
          </article>
        ))}
      </section>
    </>
  );
}
