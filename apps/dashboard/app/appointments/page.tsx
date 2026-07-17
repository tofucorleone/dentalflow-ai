import { PageHeader } from "@/components/page-header";
import { WeekCalendar } from "@/components/week-calendar";
import {
  getAppointments,
  getPatients,
  getPractitioners,
  getTreatments,
} from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AppointmentsPage() {
  const [
    appointments,
    patients,
    practitioners,
    treatments,
  ] = await Promise.all([
    getAppointments(),
    getPatients(),
    getPractitioners(),
    getTreatments(),
  ]);

  const activeAppointments = appointments.filter(
    (appointment) =>
      appointment.status === "confirmed" ||
      appointment.status === "pending",
  );

  return (
    <>
      <PageHeader
        title="Calendrier"
        description="Créez, déplacez ou annulez les rendez-vous avec synchronisation Google Calendar."
      />

      <WeekCalendar
        initialAppointments={activeAppointments}
        patients={patients}
        practitioners={practitioners}
        treatments={treatments}
      />
    </>
  );
}
