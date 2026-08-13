import Link from "next/link";
import {
  CalendarCheck,
  ChevronRight,
  CircleDollarSign,
  Stethoscope,
  Users,
} from "lucide-react";

import { DashboardCopilotOverview } from "@/components/dashboard-copilot-overview";
import { StatCard } from "@/components/stat-card";
import {
  getPatients,
  getPractitioners,
  getTreatments,
} from "@/lib/api";
import {
  getAppointments,
  getClinicBranding,
} from "@/lib/server-api";

const clinicTimeZone = "Africa/Algiers";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("fr-DZ", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: clinicTimeZone,
  }).format(new Date(value));
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("fr-DZ", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: clinicTimeZone,
  }).format(new Date(value));
}

function formatDay(value: Date) {
  return new Intl.DateTimeFormat("fr-DZ", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: clinicTimeZone,
  }).format(value);
}

function dateKey(value: Date) {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: clinicTimeZone,
  }).format(value);
}

function initials(name: string | null) {
  if (!name) {
    return "P";
  }

  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase();
}

export default async function DashboardPage() {
  const [
    appointments,
    patients,
    treatments,
    practitioners,
    branding,
  ] = await Promise.all([
    getAppointments(),
    getPatients(),
    getTreatments(),
    getPractitioners(),
    getClinicBranding(),
  ]);

  const confirmed = appointments
    .filter((appointment) => appointment.status === "confirmed")
    .sort(
      (left, right) =>
        new Date(left.start_at).getTime() -
        new Date(right.start_at).getTime(),
    );

  const revenue = confirmed.reduce((sum, appointment) => {
    const treatment = treatments.find(
      (item) => item.name === appointment.treatment_name,
    );

    return sum + Number(treatment?.price ?? 0);
  }, 0);

  const today = new Date();
  const todayKey = dateKey(today);

  const todayAppointments = confirmed.filter(
    (appointment) =>
      dateKey(new Date(appointment.start_at)) === todayKey,
  );

  const schedule =
    todayAppointments.length > 0
      ? todayAppointments.slice(0, 5)
      : confirmed.slice(0, 5);

  const recentPatients = patients.slice(0, 5);

  return (
    <div className="dashboard-v2">
      <section className="dashboard-hero-v2">
        <div className="dashboard-hero-overlay" />

        <div className="dashboard-hero-content">
          <p className="dashboard-hero-eyebrow">
            {branding.display_name}
          </p>

          <h1>
            Vue d’ensemble <span aria-hidden="true">👋</span>
          </h1>

          <p>
            Activité de la clinique, patients et rendez-vous.
          </p>
        </div>

        <div className="dashboard-hero-status">
          <span className="status-dot" />
          Synchronisé
        </div>
      </section>

      <section className="stats-grid dashboard-stats-v2">
        <StatCard
          label="Rendez-vous confirmés"
          value={confirmed.length}
          detail="Tous les rendez-vous actifs"
          icon={CalendarCheck}
          tone="appointments"
        />

        <StatCard
          label="Patients actifs"
          value={patients.length}
          detail="Patients suivis"
          icon={Users}
          tone="patients"
        />

        <StatCard
          label="Soins ce mois"
          value={treatments.length}
          detail="Soins et traitements"
          icon={Stethoscope}
          tone="treatments"
        />

        <StatCard
          label="Chiffre d’affaires"
          value={`${revenue.toLocaleString("fr-DZ")} ${branding.currency_label}`}
          detail={`${practitioners.length} praticien(s)`}
          icon={CircleDollarSign}
          tone="revenue"
        />
      </section>

      <DashboardCopilotOverview />

      <section className="dashboard-panels-v2">
        <article className="dashboard-panel-v2 appointments-panel-v2">
          <header className="dashboard-panel-heading-v2">
            <div>
              <p className="dashboard-section-label appointments">
                Agenda
              </p>
              <h2>Rendez-vous récents</h2>
            </div>

            <Link
              className="dashboard-outline-link"
              href="/appointments"
            >
              Voir l’agenda complet
            </Link>
          </header>

          <div className="dashboard-appointment-list">
            {confirmed.slice(0, 5).map((appointment) => (
              <article
                className="dashboard-appointment-row"
                key={appointment.id}
              >
                <time className="appointment-time-pill">
                  {formatTime(appointment.start_at)}
                </time>

                <div className="dashboard-appointment-person">
                  <strong>
                    {appointment.patient_name ?? "Patient"}
                  </strong>
                  <span>
                    {appointment.treatment_name ?? "Consultation"}
                    {" · "}
                    {appointment.practitioner_name ?? "Praticien"}
                  </span>
                </div>

                <time className="appointment-date">
                  {formatDateTime(appointment.start_at)}
                </time>

                <span className="badge success">Confirmé</span>
              </article>
            ))}

            {confirmed.length === 0 ? (
              <p className="dashboard-empty-state">
                Aucun rendez-vous confirmé.
              </p>
            ) : null}
          </div>

          <Link
            className="dashboard-panel-footer-link"
            href="/appointments"
          >
            Voir plus de rendez-vous
            <ChevronRight size={17} />
          </Link>
        </article>

        <article className="dashboard-panel-v2 patients-panel-v2">
          <header className="dashboard-panel-heading-v2">
            <div>
              <p className="dashboard-section-label patients">
                Patients récents
              </p>
            </div>

            <Link
              className="dashboard-outline-link patients"
              href="/patients"
            >
              Voir tous les patients
            </Link>
          </header>

          <div className="dashboard-patient-list">
            {recentPatients.map((patient, index) => (
              <Link
                className="dashboard-patient-row"
                href={`/patients/${patient.id}`}
                key={patient.id}
              >
                <span
                  className={`dashboard-patient-avatar avatar-tone-${
                    (index % 5) + 1
                  }`}
                >
                  {initials(patient.full_name)}
                </span>

                <div>
                  <strong>{patient.full_name ?? "Patient"}</strong>
                  <span>{patient.phone}</span>
                </div>

                <ChevronRight size={18} />
              </Link>
            ))}

            {recentPatients.length === 0 ? (
              <p className="dashboard-empty-state">
                Aucun patient enregistré.
              </p>
            ) : null}
          </div>
        </article>

        <article className="dashboard-panel-v2 schedule-panel-v2">
          <header className="dashboard-panel-heading-v2">
            <div>
              <p className="dashboard-section-label schedule">
                {todayAppointments.length > 0
                  ? "Aujourd’hui"
                  : "Prochains rendez-vous"}
              </p>
            </div>

            <strong className="schedule-date">
              {formatDay(today)}
            </strong>
          </header>

          <div className="dashboard-schedule-list">
            {schedule.map((appointment, index) => (
              <article
                className={`dashboard-schedule-row schedule-tone-${
                  (index % 4) + 1
                }`}
                key={appointment.id}
              >
                <time>{formatTime(appointment.start_at)}</time>

                <span className="schedule-dot" />

                <div>
                  <strong>
                    {appointment.patient_name ?? "Patient"}
                  </strong>
                  <span>
                    {appointment.treatment_name ?? "Consultation"}
                    {" · "}
                    {appointment.practitioner_name ?? "Praticien"}
                  </span>
                </div>

                <CalendarCheck size={20} />
              </article>
            ))}

            {schedule.length === 0 ? (
              <p className="dashboard-empty-state">
                Aucun rendez-vous planifié.
              </p>
            ) : null}
          </div>

          <Link
            className="dashboard-panel-footer-link"
            href="/appointments"
          >
            Voir l’agenda complet
            <ChevronRight size={17} />
          </Link>
        </article>
      </section>
    </div>
  );
}
