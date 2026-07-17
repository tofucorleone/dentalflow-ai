"use client";

import { useMemo, useState, useTransition } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Trash2 } from "lucide-react";
import type {
  Appointment,
  Patient,
  Practitioner,
  Treatment,
} from "@/lib/api";

const START_HOUR = 8;
const END_HOUR = 20;
const SLOT_MINUTES = 15;
const SLOT_HEIGHT = 18;
const DAY_COLUMN_WIDTH = 150;

type Props = {
  initialAppointments: Appointment[];
  patients: Patient[];
  practitioners: Practitioner[];
  treatments: Treatment[];
};

type DragPayload = {
  appointmentId: string;
  durationMinutes: number;
};

const locale = "fr-DZ";
const timezone = "Africa/Algiers";

function startOfWeek(value: Date): Date {
  const copy = new Date(value);
  const day = copy.getDay();
  const delta = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + delta);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays(value: Date, days: number): Date {
  const copy = new Date(value);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function localParts(value: string) {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

  const parts = Object.fromEntries(
    formatter
      .formatToParts(new Date(value))
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );

  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    hour: Number(parts.hour),
    minute: Number(parts.minute),
  };
}

function formatDateKey(value: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(value);
}

function toOffsetIso(dateKey: string, hour: number, minute: number): string {
  // The current clinic timezone is Africa/Algiers (UTC+1).
  const hh = String(hour).padStart(2, "0");
  const mm = String(minute).padStart(2, "0");
  return `${dateKey}T${hh}:${mm}:00+01:00`;
}

function durationMinutes(appointment: Appointment): number {
  return Math.max(
    SLOT_MINUTES,
    Math.round(
      (new Date(appointment.end_at).getTime() -
        new Date(appointment.start_at).getTime()) /
        60000,
    ),
  );
}

function errorMessage(body: unknown): string {
  if (
    body &&
    typeof body === "object" &&
    "detail" in body
  ) {
    const detail = (body as { detail: unknown }).detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (
      detail &&
      typeof detail === "object" &&
      "message" in detail &&
      typeof (detail as { message: unknown }).message === "string"
    ) {
      return (detail as { message: string }).message;
    }
  }

  return "L'opération a échoué.";
}

export function WeekCalendar({
  initialAppointments,
  patients,
  practitioners,
  treatments,
}: Props) {
  const [appointments, setAppointments] =
    useState<Appointment[]>(initialAppointments);
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [message, setMessage] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<{
    dateKey: string;
    hour: number;
    minute: number;
  } | null>(null);

  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [selectedPractitionerId, setSelectedPractitionerId] =
    useState("");
  const [selectedTreatmentId, setSelectedTreatmentId] =
    useState("");

  const [isPending, startTransition] = useTransition();

  const days = useMemo(
    () => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
    [weekStart],
  );

  const slots = useMemo(
    () =>
      Array.from(
        {
          length:
            ((END_HOUR - START_HOUR) * 60) / SLOT_MINUTES,
        },
        (_, index) => {
          const total = START_HOUR * 60 + index * SLOT_MINUTES;
          return {
            hour: Math.floor(total / 60),
            minute: total % 60,
          };
        },
      ),
    [],
  );

  const visibleAppointments = appointments.filter((appointment) => {
    const date = localParts(appointment.start_at).date;
    return days.some((day) => formatDateKey(day) === date);
  });

  function onDragStart(
    event: React.DragEvent,
    appointment: Appointment,
  ) {
    const payload: DragPayload = {
      appointmentId: appointment.id,
      durationMinutes: durationMinutes(appointment),
    };

    event.dataTransfer.setData(
      "application/x-dentalflow-appointment",
      JSON.stringify(payload),
    );
    event.dataTransfer.effectAllowed = "move";
  }

  function onDrop(
    event: React.DragEvent,
    dateKey: string,
    hour: number,
    minute: number,
  ) {
    event.preventDefault();
    setMessage(null);

    const raw = event.dataTransfer.getData(
      "application/x-dentalflow-appointment",
    );

    if (!raw) return;

    const payload = JSON.parse(raw) as DragPayload;
    const current = appointments.find(
      (appointment) => appointment.id === payload.appointmentId,
    );

    if (!current) return;

    const startAt = toOffsetIso(dateKey, hour, minute);

    startTransition(async () => {
      const response = await fetch(
        `/api/appointments/${encodeURIComponent(
          payload.appointmentId,
        )}/reschedule`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ start_at: startAt }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setMessage(errorMessage(body));
        return;
      }

      setAppointments((items) =>
        items.map((appointment) =>
          appointment.id === payload.appointmentId
            ? {
                ...appointment,
                start_at: body.start_at,
                end_at: body.end_at,
              }
            : appointment,
        ),
      );

      setMessage("Rendez-vous déplacé et Google Calendar synchronisé.");
    });
  }

  function cancelAppointment(appointment: Appointment) {
    const confirmed = window.confirm(
      `Annuler le rendez-vous de ${
        appointment.patient_name ?? "ce patient"
      } ?`,
    );

    if (!confirmed) return;

    setMessage(null);

    startTransition(async () => {
      const response = await fetch(
        `/api/appointments/${encodeURIComponent(
          appointment.id,
        )}/cancel`,
        { method: "DELETE" },
      );

      const body = await response.json();

      if (!response.ok) {
        setMessage(errorMessage(body));
        return;
      }

      setAppointments((items) =>
        items.filter((item) => item.id !== appointment.id),
      );
      setMessage("Rendez-vous annulé dans DentalFlow et Google Calendar.");
    });
  }


  function createAppointment(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!selectedSlot || !selectedPatientId) {
      return;
    }

    const startAt = toOffsetIso(
      selectedSlot.dateKey,
      selectedSlot.hour,
      selectedSlot.minute,
    );

    startTransition(async () => {
      const response = await fetch(
        "/api/appointments",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            patient_id: selectedPatientId,
            practitioner_id:
              selectedPractitionerId || null,
            treatment_id:
              selectedTreatmentId || null,
            channel: "dashboard",
            status: "confirmed",
            start_at: startAt,
            end_at: null,
            notes: null,
          }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setMessage(errorMessage(body));
        return;
      }

      setAppointments((items) => [...items, body]);
      setSelectedSlot(null);
      setSelectedPatientId("");
      setSelectedPractitionerId("");
      setSelectedTreatmentId("");
      setMessage(
        "Rendez-vous créé et Google Calendar synchronisé.",
      );
    });
  }

  return (
    <section className="calendar-shell">
      <div className="calendar-toolbar">
        <div>
          <p className="eyebrow">Agenda clinique</p>
          <h2>
            {new Intl.DateTimeFormat(locale, {
              day: "2-digit",
              month: "long",
              year: "numeric",
            }).format(weekStart)}
            {" — "}
            {new Intl.DateTimeFormat(locale, {
              day: "2-digit",
              month: "long",
              year: "numeric",
            }).format(addDays(weekStart, 6))}
          </h2>
        </div>

        <div className="calendar-actions">
          <button
            type="button"
            onClick={() => setWeekStart(addDays(weekStart, -7))}
          >
            <ChevronLeft size={17} />
          </button>
          <button
            type="button"
            className="today-button"
            onClick={() => setWeekStart(startOfWeek(new Date()))}
          >
            Aujourd'hui
          </button>
          <button
            type="button"
            onClick={() => setWeekStart(addDays(weekStart, 7))}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>

      {message && (
        <div className={message.includes("synchronisé") || message.includes("annulé") ? "calendar-message success-message" : "calendar-message error-message"}>
          {message}
        </div>
      )}

      {isPending && (
        <div className="calendar-loading">
          Synchronisation en cours…
        </div>
      )}

      {selectedSlot && (
        <form
          className="calendar-message success-message"
          onSubmit={createAppointment}
        >
          <strong>
            Nouveau rendez-vous — {selectedSlot.dateKey} à{" "}
            {String(selectedSlot.hour).padStart(2, "0")}:
            {String(selectedSlot.minute).padStart(2, "0")}
          </strong>

          <select
            value={selectedPatientId}
            onChange={(event) =>
              setSelectedPatientId(event.target.value)
            }
            required
          >
            <option value="">Choisir un patient</option>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.full_name ?? patient.phone}
              </option>
            ))}
          </select>

          <select
            value={selectedTreatmentId}
            onChange={(event) =>
              setSelectedTreatmentId(event.target.value)
            }
          >
            <option value="">Consultation générale</option>
            {treatments.map((treatment) => (
              <option key={treatment.id} value={treatment.id}>
                {treatment.name}
              </option>
            ))}
          </select>

          <select
            value={selectedPractitionerId}
            onChange={(event) =>
              setSelectedPractitionerId(event.target.value)
            }
          >
            <option value="">Praticien automatique</option>
            {practitioners.map((practitioner) => (
              <option
                key={practitioner.id}
                value={practitioner.id}
              >
                {practitioner.full_name}
              </option>
            ))}
          </select>

          <button type="submit">
            Créer le rendez-vous
          </button>

          <button
            type="button"
            onClick={() => setSelectedSlot(null)}
          >
            Annuler
          </button>
        </form>
      )}

      <div className="calendar-scroll">
        <div
          className="calendar-grid"
          style={{
            gridTemplateColumns: `72px repeat(7, minmax(${DAY_COLUMN_WIDTH}px, 1fr))`,
          }}
        >
          <div className="calendar-corner">
            <CalendarDays size={18} />
          </div>

          {days.map((day) => (
            <div className="calendar-day-header" key={day.toISOString()}>
              <span>
                {new Intl.DateTimeFormat(locale, {
                  weekday: "short",
                }).format(day)}
              </span>
              <strong>
                {new Intl.DateTimeFormat(locale, {
                  day: "2-digit",
                  month: "2-digit",
                }).format(day)}
              </strong>
            </div>
          ))}

          <div className="time-column">
            {slots.map((slot, index) => (
              <div
                className="time-label"
                key={`${slot.hour}-${slot.minute}`}
                style={{ height: SLOT_HEIGHT }}
              >
                {slot.minute === 0
                  ? `${String(slot.hour).padStart(2, "0")}:00`
                  : ""}
              </div>
            ))}
          </div>

          {days.map((day) => {
            const dateKey = formatDateKey(day);

            return (
              <div className="day-column" key={dateKey}>
                {slots.map((slot) => (
                  <button
                    type="button"
                    className="calendar-slot"
                    aria-label={`Créer un rendez-vous le ${dateKey} à ${String(
                      slot.hour,
                    ).padStart(2, "0")}:${String(slot.minute).padStart(
                      2,
                      "0",
                    )}`}
                    key={`${dateKey}-${slot.hour}-${slot.minute}`}
                    style={{ height: SLOT_HEIGHT }}
                    onDragOver={(event) => {
                      event.preventDefault();
                      event.dataTransfer.dropEffect = "move";
                    }}
                    onDrop={(event) =>
                      onDrop(
                        event,
                        dateKey,
                        slot.hour,
                        slot.minute,
                      )
                    }
                    onClick={() =>
                      setSelectedSlot({
                        dateKey,
                        hour: slot.hour,
                        minute: slot.minute,
                      })
                    }
                  />
                ))}

                {visibleAppointments
                  .filter(
                    (appointment) =>
                      localParts(appointment.start_at).date === dateKey,
                  )
                  .map((appointment) => {
                    const parts = localParts(appointment.start_at);
                    const startMinutes =
                      (parts.hour - START_HOUR) * 60 +
                      parts.minute;
                    const duration = durationMinutes(appointment);
                    const top =
                      (startMinutes / SLOT_MINUTES) * SLOT_HEIGHT;
                    const height = Math.max(
                      34,
                      (duration / SLOT_MINUTES) * SLOT_HEIGHT,
                    );

                    if (
                      parts.hour < START_HOUR ||
                      parts.hour >= END_HOUR
                    ) {
                      return null;
                    }

                    return (
                      <article
                        className="calendar-event"
                        draggable
                        key={appointment.id}
                        style={{ top, height }}
                        onDragStart={(event) =>
                          onDragStart(event, appointment)
                        }
                        title="Glissez pour déplacer"
                      >
                        <button
                          className="event-delete"
                          type="button"
                          title="Annuler"
                          onClick={(event) => {
                            event.stopPropagation();
                            cancelAppointment(appointment);
                          }}
                        >
                          <Trash2 size={13} />
                        </button>

                        <strong>
                          {appointment.patient_name ?? "Patient"}
                        </strong>
                        <span>
                          {appointment.treatment_name ??
                            "Consultation"}
                        </span>
                        <small>
                          {String(parts.hour).padStart(2, "0")}:
                          {String(parts.minute).padStart(2, "0")}
                          {" · "}
                          {appointment.practitioner_name ??
                            "Praticien"}
                        </small>
                      </article>
                    );
                  })}
              </div>
            );
          })}
        </div>
      </div>

      <p className="calendar-help">
        Glissez un rendez-vous vers un autre créneau. Les horaires,
        congés et conflits sont vérifiés avant toute modification.
      </p>
    </section>
  );
}
