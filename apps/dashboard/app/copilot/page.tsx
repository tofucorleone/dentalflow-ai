import Link from "next/link";

import {
  Bot,
  CalendarClock,
  LockKeyhole,
  MessageSquareText,
  Sparkles,
  UserRoundSearch,
} from "lucide-react";

import { CopilotChatPanel } from "@/components/copilot-chat-panel";
import { CopilotDraftActions } from "@/components/copilot-draft-actions";
import { CopilotOverdueDraftActions } from "@/components/copilot-overdue-draft-actions";
import { CopilotTaskCenter } from "@/components/copilot-task-center";
import { PageHeader } from "@/components/page-header";
import {
  getCopilotDailyBrief,
  getCopilotTasks,
  type CopilotRecallCandidate,
  type CopilotReleasedSlot,
} from "@/lib/server-api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function formatSlotDate(
  value: string,
  timezone: string,
): string {
  return new Intl.DateTimeFormat("fr-DZ", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone,
  }).format(new Date(value));
}

function formatRecallDate(
  value: string,
  timezone: string,
): string {
  return new Intl.DateTimeFormat("fr-DZ", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: timezone,
  }).format(new Date(value));
}

function candidateLabel(
  candidate: CopilotRecallCandidate,
): string {
  return candidate.match_level === "primary"
    ? "Correspondance principale"
    : "Correspondance secondaire";
}

function candidateTone(
  candidate: CopilotRecallCandidate,
): string {
  return candidate.match_level === "primary"
    ? "primary"
    : "secondary";
}

function ReleasedSlotCard({
  slot,
  timezone,
}: {
  slot: CopilotReleasedSlot;
  timezone: string;
}) {
  return (
    <article className="copilot-slot-card">
      <div className="copilot-slot-heading">
        <div className="copilot-slot-icon">
          <CalendarClock size={20} />
        </div>

        <div>
          <p>Créneau libéré</p>
          <h2>{formatSlotDate(slot.start_at, timezone)}</h2>
          <span>
            {slot.practitioner_name ?? "Praticien à définir"}
          </span>
        </div>
      </div>

      {slot.recall_candidates.length === 0 ? (
        <div className="copilot-empty-state">
          <UserRoundSearch size={22} />
          <div>
            <strong>Aucun candidat suffisamment compatible</strong>
            <p>
              Le Copilote ne propose aucun patient lorsque les
              préférences ou le score sont insuffisants.
            </p>
          </div>
        </div>
      ) : (
        <div className="copilot-candidate-list">
          {slot.recall_candidates.map((candidate) => (
            <section
              className="copilot-candidate-card"
              key={candidate.patient_id}
            >
              <div className="copilot-candidate-top">
                <div>
                  <span
                    className={`copilot-match-badge ${candidateTone(
                      candidate,
                    )}`}
                  >
                    {candidateLabel(candidate)}
                  </span>

                  <h3>
                    {candidate.patient_name ?? "Patient sans nom"}
                  </h3>
                </div>
              </div>

              <ul className="copilot-benefits">
                {candidate.reasons.map((reason) => (
                  <li key={reason}>✓ {reason}</li>
                ))}
              </ul>

              <div className="copilot-draft">
                <div className="copilot-draft-title">
                  <MessageSquareText size={18} />
                  <strong>Brouillon WhatsApp</strong>
                </div>

                <pre>{candidate.draft_message}</pre>

                <CopilotDraftActions
                  patientId={candidate.patient_id}
                  appointmentId={slot.appointment_id}
                  practitionerId={slot.practitioner_id}
                  treatmentId={slot.treatment_id}
                  startAt={slot.start_at}
                  endAt={slot.end_at}
                  draftMessage={candidate.draft_message}
                  candidateScore={candidate.score}
                  matchLevel={candidate.match_level}
                  reasons={candidate.reasons}
                  requiresValidation={
                    candidate.requires_validation
                  }
                />
              </div>

              {candidate.requires_validation && (
                <div className="copilot-validation">
                  <LockKeyhole size={16} />
                  Validation humaine requise avant tout envoi
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </article>
  );
}

export default async function CopilotPage() {
  const [brief, tasks] = await Promise.all([
    getCopilotDailyBrief(),
    getCopilotTasks(),
  ]);

  return (
    <>
      <PageHeader
        title="Copilote DentalFlow AI"
        description="Priorités, créneaux libérés et propositions préparées pour validation humaine."
      />

      <CopilotChatPanel />


      <CopilotTaskCenter tasks={tasks} />

      <section className="copilot-summary-grid">
        <article className="copilot-summary-card">
          <Bot size={22} />
          <span>Actions proposées</span>
          <strong>{brief.actions.length}</strong>
        </article>

        <article className="copilot-summary-card">
          <CalendarClock size={22} />
          <span>Créneaux libérés</span>
          <strong>{brief.released_slots.length}</strong>
        </article>

          <article className="copilot-summary-card">
            <UserRoundSearch size={22} />
            <span>Patients à recontacter</span>
            <strong>
              {brief.overdue_recall_patients.length}
            </strong>
          </article>
      </section>

      <section className="copilot-actions-panel">
        <div className="copilot-actions-heading">
          <div>
            <span>Priorités du jour</span>
            <h2>Actions proposées</h2>
          </div>

          <strong>{brief.actions.length}</strong>
        </div>

        {brief.actions.length === 0 ? (
          <div className="copilot-actions-empty">
            Aucune action prioritaire pour le moment.
          </div>
        ) : (
          <div className="copilot-actions-list">
            {brief.actions.map((action) => (
              <article
                className={`copilot-action-card ${action.priority}`}
                key={action.id}
              >
                <div className="copilot-action-main">
                  <div className="copilot-action-meta">
                    <span className="copilot-action-priority">
                      {action.priority === "high"
                        ? "Priorité haute"
                        : action.priority === "medium"
                          ? "Priorité moyenne"
                          : "Priorité basse"}
                    </span>

                    <span className="copilot-action-score">
                      Score {action.score}
                    </span>
                  </div>

                  <h3>{action.title}</h3>
                  <p>{action.description}</p>
                  <strong>{action.recommended_action}</strong>
                </div>

                {action.requires_validation && (
                  <div className="copilot-action-validation">
                    <LockKeyhole size={15} />
                    Validation requise
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="copilot-overdue-panel">
        <div className="copilot-overdue-heading">
          <div>
            <span>Suivi préventif</span>
            <h2>Patients à recontacter</h2>
            <p>
              Patients actifs sans rendez-vous futur dont la
              dernière visite terminée remonte à plus de 12 mois.
            </p>
          </div>

          <strong>
            {brief.overdue_recall_patients.length}
          </strong>
        </div>

        {brief.overdue_recall_patients.length === 0 ? (
          <div className="copilot-overdue-empty">
            Aucun patient à recontacter pour le moment.
          </div>
        ) : (
          <div className="copilot-overdue-list">
            {brief.overdue_recall_patients.map((patient) => (
              <article
                className="copilot-overdue-card"
                key={patient.patient_id}
              >
                <div className="copilot-overdue-avatar">
                  {(patient.patient_name ?? "P")
                    .slice(0, 1)
                    .toUpperCase()}
                </div>

                <div className="copilot-overdue-main">
                  <div className="copilot-overdue-meta">
                    <span
                      className={`copilot-overdue-priority ${patient.priority}`}
                    >
                      {patient.priority === "high"
                        ? "Priorité haute"
                        : patient.priority === "medium"
                          ? "Priorité moyenne"
                          : "Priorité basse"}
                    </span>

                    <span className="copilot-overdue-score">
                      Score {patient.score}
                    </span>
                  </div>

                  <h3>
                    {patient.patient_name ?? "Patient sans nom"}
                  </h3>

                  <p>
                    Dernière visite terminée le{" "}
                    <strong>
                      {formatRecallDate(
                        patient.last_completed_at,
                        brief.timezone,
                      )}
                    </strong>
                  </p>

                  <ul className="copilot-overdue-reasons">
                    {patient.reasons.map((reason) => (
                      <li key={reason}>✓ {reason}</li>
                    ))}
                  </ul>

                  <div className="copilot-overdue-action-center">
                    <div className="copilot-overdue-contact">
                      <span>{patient.phone}</span>

                      {patient.email ? (
                        <span>{patient.email}</span>
                      ) : null}
                    </div>

                    <CopilotOverdueDraftActions
                      draftMessage={patient.draft_message}
                    />

                    <div className="copilot-overdue-card-actions">
                      <div
                      style={{
                        display: "flex",
                        gap: "10px",
                        marginTop: "12px",
                        flexWrap: "wrap",
                      }}
                    >
                      <a
                        className="copilot-overdue-link"
                        href={`tel:${patient.phone}`}
                      >
                        📞 Appeler
                      </a>

                      <Link
                        className="copilot-overdue-link"
                        href={`/patients/${patient.patient_id}`}
                      >
                        👤 Voir la fiche
                      </Link>
                    </div>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>


      <section className="copilot-slots-grid">
        {brief.released_slots.map((slot) => (
          <ReleasedSlotCard
            key={slot.appointment_id}
            slot={slot}
            timezone={brief.timezone}
          />
        ))}
      </section>
    </>
  );
}
