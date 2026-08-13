"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useSearchParams } from "next/navigation";
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
const SLOT_WIDTH = 28;
const DAY_ROW_HEIGHT = 96;
const DAY_LABEL_WIDTH = 104;

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

function practitionerTone(
  practitionerName: string | null,
): number {
  const value = practitionerName?.trim() || "Praticien";
  let hash = 0;

  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }

  return (hash % 6) + 1;
}


type PositionedAppointment = {
  appointment: Appointment;
  columnIndex: number;
  columnCount: number;
};

function layoutDayAppointments(
  appointments: Appointment[],
): PositionedAppointment[] {
  const sorted = [...appointments].sort(
    (left, right) =>
      new Date(left.start_at).getTime() -
      new Date(right.start_at).getTime(),
  );

  const positioned: PositionedAppointment[] = [];
  let group: Appointment[] = [];
  let groupEnd = Number.NEGATIVE_INFINITY;

  function flushGroup() {
    if (group.length === 0) {
      return;
    }

    const columnEnds: number[] = [];
    const temporary: Array<{
      appointment: Appointment;
      columnIndex: number;
    }> = [];

    for (const appointment of group) {
      const start = new Date(appointment.start_at).getTime();
      const end = new Date(appointment.end_at).getTime();

      let columnIndex = columnEnds.findIndex(
        (columnEnd) => columnEnd <= start,
      );

      if (columnIndex === -1) {
        columnIndex = columnEnds.length;
        columnEnds.push(end);
      } else {
        columnEnds[columnIndex] = end;
      }

      temporary.push({
        appointment,
        columnIndex,
      });
    }

    const columnCount = Math.max(1, columnEnds.length);

    positioned.push(
      ...temporary.map((item) => ({
        ...item,
        columnCount,
      })),
    );
  }

  for (const appointment of sorted) {
    const start = new Date(appointment.start_at).getTime();
    const end = new Date(appointment.end_at).getTime();

    if (group.length > 0 && start >= groupEnd) {
      flushGroup();
      group = [];
      groupEnd = Number.NEGATIVE_INFINITY;
    }

    group.push(appointment);
    groupEnd = Math.max(groupEnd, end);
  }

  flushGroup();

  return positioned;
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
  const searchParams = useSearchParams();
  const [appointments, setAppointments] =
    useState<Appointment[]>(initialAppointments);
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [message, setMessage] = useState<string | null>(null);
  const [appointmentPendingCancel, setAppointmentPendingCancel] =
    useState<Appointment | null>(null);

  const [pendingRescheduleSlot, setPendingRescheduleSlot] =
    useState<{
      dateKey: string;
      hour: number;
      minute: number;
    } | null>(null);
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
  const [selectedPractitionerFilter, setSelectedPractitionerFilter] =
    useState("all");

  const [isPending, startTransition] = useTransition();

  const copilotMode = searchParams.get("mode");
  const copilotAppointmentId =
    searchParams.get("appointment_id")?.trim() ?? "";
  const copilotThreadId =
    searchParams.get("thread_id")?.trim() ?? "";
  const copilotRescheduleAppointment =
    copilotMode === "reschedule" && copilotAppointmentId
      ? appointments.find(
          (appointment) => appointment.id === copilotAppointmentId,
        ) ?? null
      : null;

  useEffect(() => {
    const patientId = searchParams.get("patient_id")?.trim() ?? "";

    if (!patientId) {
      return;
    }

    const patientExists = patients.some(
      (patient) => patient.id === patientId,
    );

    if (!patientExists) {
      setMessage("Le patient proposé par le Copilote est introuvable.");
      return;
    }

    setSelectedPatientId(patientId);

    if (copilotMode === "reschedule") {
      const appointment = initialAppointments.find(
        (item) => item.id === copilotAppointmentId,
      );

      if (!appointment) {
        setMessage(
          "Le rendez-vous proposé par le Copilote est introuvable.",
        );
        return;
      }

      setWeekStart(startOfWeek(new Date(appointment.start_at)));
      setMessage(
        "Déplacement préparé par le Copilote. Choisissez le nouveau créneau puis confirmez.",
      );
      return;
    }

    setMessage(
      "Patient sélectionné par le Copilote. Choisissez un créneau puis confirmez la création.",
    );
  }, [
    copilotAppointmentId,
    copilotMode,
    initialAppointments,
    patients,
    searchParams,
  ]);

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

  const visibleAppointments = appointments.filter(
    (appointment) => {
      const date = localParts(appointment.start_at).date;

      const isInsideCurrentWeek = days.some(
        (day) => formatDateKey(day) === date,
      );

      const matchesPractitioner =
        selectedPractitionerFilter === "all" ||
        appointment.practitioner_name ===
          selectedPractitionerFilter;

      return isInsideCurrentWeek && matchesPractitioner;
    },
  );

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

    const previousStartAt = current.start_at;
    const previousEndAt = current.end_at;

    const previousDurationMs =
      new Date(previousEndAt).getTime() -
      new Date(previousStartAt).getTime();

    const optimisticEndAt = new Date(
      new Date(startAt).getTime() + previousDurationMs,
    ).toISOString();

    setAppointments((items) =>
      items.map((appointment) =>
        appointment.id === payload.appointmentId
          ? {
              ...appointment,
              start_at: startAt,
              end_at: optimisticEndAt,
            }
          : appointment,
      ),
    );

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
        setAppointments((items) =>
          items.map((appointment) =>
            appointment.id === payload.appointmentId
              ? {
                  ...appointment,
                  start_at: previousStartAt,
                  end_at: previousEndAt,
                }
              : appointment,
          ),
        );

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
    setAppointmentPendingCancel(appointment);
  }

  function confirmCancelAppointment() {
    const appointment = appointmentPendingCancel;

    if (!appointment) return;

    setAppointmentPendingCancel(null);
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


  function confirmCopilotReschedule(slot: {
    dateKey: string;
    hour: number;
    minute: number;
  }) {
    if (!copilotRescheduleAppointment) {
      return;
    }

    setPendingRescheduleSlot(slot);
  }

  function executeCopilotReschedule() {
    if (
      !copilotRescheduleAppointment ||
      !pendingRescheduleSlot
    ) {
      return;
    }

    const slot = pendingRescheduleSlot;

    const startAt = toOffsetIso(
      slot.dateKey,
      slot.hour,
      slot.minute,
    );

    setPendingRescheduleSlot(null);

    setSelectedSlot(slot);
    setMessage(null);

    startTransition(async () => {
      const response = await fetch(
        `/api/appointments/${encodeURIComponent(
          copilotRescheduleAppointment.id,
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
          appointment.id === copilotRescheduleAppointment.id
            ? {
                ...appointment,
                start_at: body.start_at,
                end_at: body.end_at,
              }
            : appointment,
        ),
      );
      setSelectedSlot(null);
      setMessage(
        "Rendez-vous déplacé et Google Calendar synchronisé. Retour à la conversation…",
      );

      window.setTimeout(() => {
        if (copilotThreadId) {
          window.location.href = `/conversations?thread_id=${encodeURIComponent(
            copilotThreadId,
          )}`;
          return;
        }

        window.location.href = "/appointments";
      }, 700);
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


  function markAppointmentNoShow(
    appointment: Appointment,
  ) {
    const confirmed = window.confirm(
      `Marquer ${
        appointment.patient_name ?? "ce patient"
      } comme absent ?`,
    );

    if (!confirmed) return;

    setMessage(null);

    startTransition(async () => {
      const response = await fetch(
        `/api/appointments/${encodeURIComponent(
          appointment.id,
        )}/no-show`,
        {
          method: "PATCH",
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setMessage(errorMessage(body));
        return;
      }

      setAppointments((items) =>
        items.map((item) =>
          item.id === appointment.id
            ? {
                ...item,
                status: "no_show",
              }
            : item,
        ),
      );

      setMessage(
        "Rendez-vous marqué comme absent.",
      );
    });
  }


  return (
    <section className="calendar-shell">
      <div className="calendar-toolbar">
        <div className="calendar-toolbar-main">
            <p className="eyebrow">Agenda clinique</p>

            <label className="calendar-practitioner-filter">
              <span>Praticien :</span>
              <select
                value={selectedPractitionerFilter}
                onChange={(event) =>
                  setSelectedPractitionerFilter(event.target.value)
                }
              >
                <option value="all">Tous les praticiens</option>
                {practitioners.map((practitioner) => (
                  <option
                    key={practitioner.id}
                    value={practitioner.full_name}
                  >
                    {practitioner.full_name}
                  </option>
                ))}
              </select>
            </label>

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

      {selectedSlot && !copilotRescheduleAppointment && (
        <form
          className="calendar-message success-message"
          onSubmit={createAppointment}
        >
          <strong>
            Nouveau rendez-vous — {selectedSlot.dateKey} à{" "}
            {String(selectedSlot.hour).padStart(2, "0")}:
            {String(selectedSlot.minute).padStart(2, "0")}
          </strong>

          <>
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
            </>

          <button type="submit">Créer le rendez-vous</button>

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
          className="calendar-grid calendar-grid-horizontal"
          style={{
            gridTemplateColumns:
              `${DAY_LABEL_WIDTH}px ${slots.length * SLOT_WIDTH}px`,
            gridTemplateRows:
              `58px repeat(7, ${DAY_ROW_HEIGHT}px)`,
          }}
        >
          <div className="calendar-corner">
            <CalendarDays size={18} />
          </div>

          {days.map((day, dayIndex) => (
            <div
              className="calendar-day-header"
              key={day.toISOString()}
              style={{
                gridColumn: 1,
                gridRow: dayIndex + 2,
              }}
            >
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

          <div
            className="time-column"
            style={{
              gridColumn: 2,
              gridRow: 1,
            }}
          >
            {Array.from(
              { length: END_HOUR - START_HOUR },
              (_, index) => START_HOUR + index,
            ).map((hour) => (
              <div
                className="time-label"
                key={hour}
                style={{
                  width:
                    (60 / SLOT_MINUTES) * SLOT_WIDTH,
                }}
              >
                {`${String(hour).padStart(2, "0")}:00`}
              </div>
            ))}
          </div>

          {days.map((day, dayIndex) => {
            const dateKey = formatDateKey(day);

            return (
              <div
                className="day-column"
                key={dateKey}
                style={{
                  gridColumn: 2,
                  gridRow: dayIndex + 2,
                  width: slots.length * SLOT_WIDTH,
                  height: DAY_ROW_HEIGHT,
                }}
              >
                {slots.map((slot) => (
                  <button
                    type="button"
                    className="calendar-slot"
                    aria-label={`${
                      copilotRescheduleAppointment
                        ? "Déplacer le rendez-vous au"
                        : "Créer un rendez-vous le"
                    } ${dateKey} à ${String(slot.hour).padStart(
                      2,
                      "0",
                    )}:00`}
                    key={`${dateKey}-${slot.hour}-${slot.minute}`}
                    style={{
                      width: SLOT_WIDTH,
                      height: DAY_ROW_HEIGHT,
                    }}
                    onDragOver={(event) => {
                      event.preventDefault();
                      event.dataTransfer.dropEffect = "move";
                    }}
                    onDrop={(event) =>
                      onDrop(
                        event,
                        dateKey,
                        slot.hour,
                        0,
                      )
                    }
                    onClick={() => {
                      const targetSlot = {
                        dateKey,
                        hour: slot.hour,
                        minute: 0,
                      };

                      if (copilotRescheduleAppointment) {
                        confirmCopilotReschedule(targetSlot);
                        return;
                      }

                      setSelectedSlot(targetSlot);
                    }}
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
                    const left =
                      (startMinutes / SLOT_MINUTES) * SLOT_WIDTH;
                    const width = Math.max(
                      72,
                      (duration / SLOT_MINUTES) * SLOT_WIDTH,
                    );

                    const patientFullName = (
                      appointment.patient_name ??
                      "Patient"
                    ).trim();

                    const patientNameParts =
                      patientFullName.split(/\s+/);

                    const patientFirstName =
                      patientNameParts[0] || "Patient";

                    const patientLastName =
                      patientNameParts.slice(1).join(" ");

                    const sameSlotAppointments =
                      visibleAppointments.filter((item) => {
                        const itemParts =
                          localParts(item.start_at);

                        return (
                          itemParts.date === dateKey &&
                          itemParts.hour === parts.hour &&
                          itemParts.minute === parts.minute
                        );
                      });

                    const overlapIndex = Math.max(
                      0,
                      sameSlotAppointments.findIndex(
                        (item) =>
                          item.id === appointment.id,
                      ),
                    );

                    const overlapCount =
                      sameSlotAppointments.length;

                    // Effet marque-pages :
                    // même largeur/durée et même top,
                    // seule la hauteur diminue progressivement.
                    const stackedMinHeight = 24;
                    const visibleStackStep = 24;

                    if (
                      parts.hour < START_HOUR ||
                      parts.hour >= END_HOUR
                    ) {
                      return null;
                    }

                    return (
                      <article
                        className={`calendar-event practitioner-tone-${practitionerTone(
                            appointment.practitioner_name,
                          )}${
                            appointment.id === copilotAppointmentId &&
                            copilotMode === "reschedule"
                              ? " copilot-reschedule-target"
                              : ""
                          }`}
                        aria-current={
                          appointment.id === copilotAppointmentId &&
                          copilotMode === "reschedule"
                            ? "true"
                            : undefined
                        }
                        draggable
                        key={appointment.id}
                        data-overlap-count={overlapCount}
                        data-overlap-index={overlapIndex}
                        style={{
                          left,

                          // La largeur reste STRICTEMENT liée
                          // à la durée du soin.
                          width,

                          // Toutes les cartes commencent au même niveau.
                          top: 6,

                          // Seule la HAUTEUR diminue.
                          height: Math.max(
                            stackedMinHeight,
                            DAY_ROW_HEIGHT -
                              12 -
                              overlapIndex * visibleStackStep,
                          ),

                          // La carte suivante passe devant.
                          zIndex:
                            overlapCount > 1
                              ? 30 + overlapIndex
                              : 5,
                        }}
                        onDragStart={(event) =>
                          onDragStart(event, appointment)
                        }
                        onClick={() => {
                          if (!appointment.patient_id) {
                            return;
                          }

                          window.location.href =
                            `/patients/${encodeURIComponent(
                              appointment.patient_id,
                            )}`;
                        }}
                        title={`${appointment.patient_name ?? "Patient"}
🦷 ${appointment.treatment_session_name ?? appointment.treatment_name ?? "Consultation"}
👨‍⚕️ ${appointment.practitioner_name ?? "Praticien"}
${String(parts.hour).padStart(2, "0")}:${String(
                            parts.minute,
                          ).padStart(2, "0")}`}
                      >
                        <button
                          className="event-reschedule"
                          type="button"
                          title="Déplacer"
                          aria-label="Déplacer le rendez-vous"
                          onClick={(event) => {
                            event.stopPropagation();

                            const params =
                              new URLSearchParams();

                            params.set(
                              "mode",
                              "reschedule",
                            );
                            params.set(
                              "appointment_id",
                              appointment.id,
                            );

                            if (appointment.patient_id) {
                              params.set(
                                "patient_id",
                                appointment.patient_id,
                              );
                            }

                            window.location.href =
                              `/appointments?${params.toString()}`;
                          }}
                        >
                          ↔
                        </button>

                        <button
                          className="event-no-show"
                          type="button"
                          title="Absent"
                          aria-label="Marquer le patient absent"
                          onClick={(event) => {
                            event.stopPropagation();
                            markAppointmentNoShow(
                              appointment,
                            );
                          }}
                        >
                          A
                        </button>

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

                        <strong className="calendar-event-patient">
                          <span>
                            {patientFirstName}
                          </span>

                          {patientLastName ? (
                            <span>
                              {patientLastName}
                            </span>
                          ) : null}
                        </strong>

                        <span className="calendar-event-treatment">
                          <span aria-hidden="true">🦷</span>
                          {appointment.treatment_session_name ?? appointment.treatment_name ?? "Consultation"}
                        </span>

                        <small className="calendar-event-practitioner">
                          <span aria-hidden="true">👨‍⚕️</span>
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

      {pendingRescheduleSlot && copilotRescheduleAppointment ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="reschedule-appointment-title"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            background: "rgba(15, 23, 42, 0.45)",
          }}
          onClick={() => setPendingRescheduleSlot(null)}
        >
          <div
            style={{
              width: "min(480px, 100%)",
              borderRadius: 18,
              padding: 24,
              background: "white",
              boxShadow: "0 24px 70px rgba(15, 23, 42, 0.25)",
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <h3
              id="reschedule-appointment-title"
              style={{ margin: "0 0 10px" }}
            >
              Déplacer le rendez-vous ?
            </h3>

            <p style={{ margin: "0 0 10px", lineHeight: 1.5 }}>
              Patient :{" "}
              <strong>
                {copilotRescheduleAppointment.patient_name ?? "ce patient"}
              </strong>
            </p>

            <p style={{ margin: "0 0 22px", lineHeight: 1.5 }}>
              Nouvel horaire :{" "}
              <strong>
                {pendingRescheduleSlot.dateKey} à{" "}
                {String(pendingRescheduleSlot.hour).padStart(2, "0")}:
                {String(pendingRescheduleSlot.minute).padStart(2, "0")}
              </strong>
            </p>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 10,
              }}
            >
              <button
                type="button"
                onClick={() => setPendingRescheduleSlot(null)}
              >
                Garder le rendez-vous
              </button>

              <button
                type="button"
                onClick={executeCopilotReschedule}
                disabled={isPending}
              >
                {isPending
                  ? "Déplacement..."
                  : "Confirmer le déplacement"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {appointmentPendingCancel ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="cancel-appointment-title"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            background: "rgba(15, 23, 42, 0.45)",
          }}
          onClick={() => setAppointmentPendingCancel(null)}
        >
          <div
            style={{
              width: "min(440px, 100%)",
              borderRadius: 18,
              padding: 24,
              background: "white",
              boxShadow: "0 24px 70px rgba(15, 23, 42, 0.25)",
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <h3
              id="cancel-appointment-title"
              style={{ margin: "0 0 10px" }}
            >
              Annuler le rendez-vous ?
            </h3>

            <p style={{ margin: "0 0 22px", lineHeight: 1.5 }}>
              Voulez-vous vraiment annuler le rendez-vous de{" "}
              <strong>
                {appointmentPendingCancel.patient_name ?? "ce patient"}
              </strong>
              {" "}?
            </p>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 10,
              }}
            >
              <button
                type="button"
                onClick={() => setAppointmentPendingCancel(null)}
              >
                Garder le rendez-vous
              </button>

              <button
                type="button"
                onClick={confirmCancelAppointment}
                disabled={isPending}
              >
                {isPending
                  ? "Annulation..."
                  : "Annuler le rendez-vous"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
