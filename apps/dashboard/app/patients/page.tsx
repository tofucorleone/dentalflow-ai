import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { getPatients } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function PatientsPage() {
  const patients = await getPatients();

  return (
    <>
      <PageHeader title="Patients" description="Répertoire administratif et fiches Patient 360°." />
      <section className="card-grid">
        {patients.map((patient) => (
          <Link className="person-card patient-link" href={`/patients/${patient.id}`} key={patient.id}>
            <div className="avatar">{(patient.full_name ?? "P").slice(0,1).toUpperCase()}</div>
            <div>
              <strong>{patient.full_name ?? "Patient sans nom"}</strong>
              <p>{patient.phone}</p>
              <span>{patient.email ?? "Aucun e-mail"}</span>
            </div>
          </Link>
        ))}
      </section>
    </>
  );
}
