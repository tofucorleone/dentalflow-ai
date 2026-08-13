import { PageHeader } from "@/components/page-header";
import { PatientDirectory } from "@/components/patient-directory";
import { getPatients } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function PatientsPage() {
  const patients = await getPatients();

  return (
    <>
      <div className="patients-page-heading">
        <PageHeader
          title="Patients"
          description="Répertoire administratif et fiches Patient 360°."
        />
      </div>

      <PatientDirectory patients={patients} />
    </>
  );
}
