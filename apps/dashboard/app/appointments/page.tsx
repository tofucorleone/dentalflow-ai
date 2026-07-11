import { PageHeader } from "@/components/page-header";
import { WeekCalendar } from "@/components/week-calendar";
import { getAppointments } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AppointmentsPage() {
  const appointments = await getAppointments();

  const activeAppointments = appointments.filter(
    (appointment) =>
      appointment.status === "confirmed" ||
      appointment.status === "pending",
  );

  return (
    <>
      <PageHeader
        title="Calendrier"
        description="Déplacez ou annulez les rendez-vous avec synchronisation Google Calendar."
      />
      <WeekCalendar initialAppointments={activeAppointments} />
    </>
  );
}
