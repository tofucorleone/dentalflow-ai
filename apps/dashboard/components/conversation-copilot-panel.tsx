"use client";

import {
  AlertTriangle,
  Bot,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  HeartPulse,
  History,
  LoaderCircle,
  Copy,
  RefreshCw,
  SendToBack,
  NotebookText,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
} from "lucide-react";
import { useEffect, useState } from "react";

export type CopilotConversationAction = {
  type:
    | "review_urgent"
    | "prepare_appointment"
    | "prepare_reschedule"
    | "prepare_cancellation"
    | "link_patient"
    | "review_conversation";
  label: string;
  description: string;
  requires_validation: boolean;
};

export type CopilotPatientAppointmentSummary = {
  id: string;
  status: "pending" | "confirmed" | "cancelled" | "completed" | "no_show";
  start_at: string;
  end_at: string;
  practitioner_name: string | null;
  treatment_name: string | null;
};

export type CopilotPatientTimelineEvent = {
  id: string;
  type: "appointment" | "conversation" | "note";
  occurred_at: string;
  title: string;
  description: string | null;
  status: string | null;
  direction: "inbound" | "outbound" | null;
};

export type CopilotPatientContext = {
  identified: boolean;
  full_name: string | null;
  phone: string | null;
  ai_summary: string | null;
  last_goal: string | null;
  preferences: Record<string, unknown>;
  recent_notes: string[];
  medical_history: string[];
  next_appointment: CopilotPatientAppointmentSummary | null;
  last_completed_appointment: CopilotPatientAppointmentSummary | null;
};

export type CopilotConversationInsight = {
  thread_id: string;
  patient_id: string | null;
  patient_name: string | null;
  sender_phone: string;
  summary: string;
  priority: "high" | "medium" | "low";
  priority_score: number;
  priority_reasons: string[];
  intents: string[];
  recommended_actions: CopilotConversationAction[];
  message_count: number;
  control_mode: "ai_active" | "human_active" | "paused" | "closed";
  last_message_at: string | null;
  patient_context: CopilotPatientContext;
  patient_timeline: CopilotPatientTimelineEvent[];
  read_only: true;
};

type CopilotAuditEvent = {
  id: string; actor_user_id: string | null; action_type: string; result: "success" | "failed" | "prepared";
  entity_type: string | null; entity_id: string | null; before_data: Record<string, unknown>; after_data: Record<string, unknown>;
  metadata: Record<string, unknown>; created_at: string;
};
type CopilotAuditListResponse = { thread_id: string; items: CopilotAuditEvent[] };
const auditLabels: Record<string, string> = { appointment_created: "Rendez-vous créé", appointment_rescheduled: "Rendez-vous déplacé", appointment_cancelled: "Rendez-vous annulé", human_takeover: "Prise en main humaine", copilot_reactivated: "Copilote réactivé" };
function auditDate(value: string): string { return new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)); }

type ConversationCopilotPanelProps = {
  threadId: string;
  refreshToken: string;
  onUseDraft: (message: string) => void;
  onPrepareAppointment: (patientId: string) => void;
  onPrepareReschedule: (patientId: string, appointmentId: string) => void;
  onControlModeChanged: (
    mode: "ai_active" | "human_active",
    takenOverByUserId: string | null,
    takenOverAt: string | null,
  ) => void;
};

type DraftTone = "professional" | "warm" | "concise";

const priorityLabels = {
  high: "Haute",
  medium: "Moyenne",
  low: "Faible",
} as const;

const intentLabels: Record<string, string> = {
  appointment_request: "Prise de rendez-vous",
  appointment_cancel: "Annulation",
  appointment_reschedule: "Déplacement",
  pain: "Douleur",
  emergency: "Urgence",
  quote: "Devis",
  payment: "Paiement",
  information: "Demande d’information",
  thanks: "Remerciement",
  complaint: "Réclamation",
};

function humanizeIntent(intent: string): string {
  return (
    intentLabels[intent] ??
    intent
      .replaceAll("_", " ")
      .replace(/^./, (character) => character.toUpperCase())
  );
}

function buildReplyDraft(
  insight: CopilotConversationInsight,
  tone: DraftTone,
): string {
  const name =
    insight.patient_context.full_name?.trim().split(/\s+/)[0] ?? null;
  const greeting = name ? `Bonjour ${name},` : "Bonjour,";
  const intents = new Set(insight.intents);

  let body =
    "nous avons bien reçu votre message. L’équipe du cabinet revient vers vous dès que possible.";

  if (intents.has("urgence_dentaire") || intents.has("emergency") || intents.has("pain")) {
    body =
      "nous avons bien reçu votre message. Votre situation nécessite une attention rapide. Pouvez-vous nous préciser depuis quand la douleur a commencé et si vous présentez un gonflement ou de la fièvre ?";
  } else if (intents.has("deplacement_rendez_vous") || intents.has("appointment_reschedule")) {
    body =
      "nous avons bien pris en compte votre demande de déplacement. Nous allons vérifier les prochains créneaux disponibles et vous proposer une nouvelle date.";
  } else if (intents.has("annulation_rendez_vous") || intents.has("appointment_cancel")) {
    body =
      "nous avons bien reçu votre demande d’annulation. Nous allons vérifier le rendez-vous concerné avant de vous confirmer sa prise en compte.";
  } else if (intents.has("prise_rendez_vous") || intents.has("appointment_request")) {
    body =
      "nous avons bien reçu votre demande de rendez-vous. Nous allons vérifier les disponibilités et vous proposer les créneaux les plus adaptés.";
  } else if (intents.has("tarif_soin") || intents.has("quote") || intents.has("payment")) {
    body =
      "nous avons bien reçu votre demande concernant le tarif. Le montant dépend du soin nécessaire ; une évaluation clinique permettra de vous communiquer une estimation précise.";
  } else if (intents.has("document")) {
    body =
      "nous avons bien reçu votre demande de document. L’équipe va vérifier votre dossier et revenir vers vous rapidement.";
  } else if (insight.priority === "high") {
    body =
      "nous avons bien reçu votre message et allons le faire examiner rapidement par l’équipe clinique.";
  }

  const closing =
    tone === "warm"
      ? "Nous restons à votre écoute.\nL’équipe du cabinet"
      : tone === "concise"
        ? "Merci.\nL’équipe du cabinet"
        : "Bien cordialement,\nL’équipe du cabinet";

  return [greeting, body, closing].join("\n\n");
}

function getErrorDetail(value: unknown): string | null {
  if (
    typeof value === "object" &&
    value !== null &&
    "detail" in value &&
    typeof value.detail === "string"
  ) {
    return value.detail;
  }

  return null;
}

export function ConversationCopilotPanel({
  threadId,
  refreshToken,
  onUseDraft,
  onPrepareAppointment,
  onPrepareReschedule,
  onControlModeChanged,
}: ConversationCopilotPanelProps) {
  const [insight, setInsight] =
    useState<CopilotConversationInsight | null>(null);
  const [replyDraft, setReplyDraft] = useState<string | null>(null);
  const [draftTone, setDraftTone] = useState<DraftTone>("professional");
  const [copyLabel, setCopyLabel] = useState("Copier");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [changingControl, setChangingControl] = useState(false);
  const [controlError, setControlError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [cancelingAppointmentId, setCancelingAppointmentId] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [auditItems, setAuditItems] = useState<CopilotAuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    async function loadInsight() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/copilot/conversations/${threadId}/insight`,
          {
            cache: "no-store",
            signal: controller.signal,
          },
        );

        const body = (await response.json()) as unknown;

        if (!response.ok) {
          throw new Error(
            getErrorDetail(body) ??
              `Analyse Copilote indisponible (${response.status}).`,
          );
        }

        setInsight(body as CopilotConversationInsight);
      } catch (caughtError) {
        if (
          caughtError instanceof DOMException &&
          caughtError.name === "AbortError"
        ) {
          return;
        }

        setInsight(null);
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger l’analyse Copilote.",
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadInsight();

    return () => controller.abort();
  }, [threadId, refreshToken, reloadToken]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadAudit() {
      setAuditLoading(true);
      try {
        const response = await fetch(`/api/copilot/conversations/${threadId}/audit`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) return;
        const body = (await response.json()) as CopilotAuditListResponse;
        setAuditItems(Array.isArray(body.items) ? body.items : []);
      } catch (caughtError) {
        if (!(caughtError instanceof DOMException && caughtError.name === "AbortError")) setAuditItems([]);
      } finally { if (!controller.signal.aborted) setAuditLoading(false); }
    }
    void loadAudit();
    return () => controller.abort();
  }, [threadId, refreshToken, reloadToken, insight?.control_mode]);

  useEffect(() => {
    setReplyDraft(null);
    setActionMessage(null);
    setActionError(null);
  }, [threadId, refreshToken, reloadToken]);

  async function cancelCopilotAppointment(appointment: CopilotPatientAppointmentSummary) {
    if (cancelingAppointmentId) return;

    const startLabel = new Intl.DateTimeFormat("fr-FR", {
      dateStyle: "full",
      timeStyle: "short",
    }).format(new Date(appointment.start_at));

    const confirmed = window.confirm(
      `Confirmer l’annulation du rendez-vous du ${startLabel} ?`,
    );

    if (!confirmed) return;

    setCancelingAppointmentId(appointment.id);
    setActionMessage(null);
    setActionError(null);

    try {
      const response = await fetch(
        `/api/appointments/${encodeURIComponent(appointment.id)}/cancel`,
        { method: "DELETE" },
      );
      const body = (await response.json()) as unknown;

      if (!response.ok) {
        throw new Error(
          getErrorDetail(body) ??
            `Annulation impossible (${response.status}).`,
        );
      }

      setActionMessage("Rendez-vous annulé avec succès.");
      setReloadToken((value) => value + 1);
    } catch (caughtError) {
      setActionError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d’annuler le rendez-vous.",
      );
    } finally {
      setCancelingAppointmentId(null);
    }
  }

  async function copyDraft() {
    if (!replyDraft) return;
    await navigator.clipboard.writeText(replyDraft);
    setCopyLabel("Copié");
    window.setTimeout(() => setCopyLabel("Copier"), 1400);
  }

  async function changeControlMode(
    mode: "ai_active" | "human_active",
  ) {
    if (changingControl) return;

    setChangingControl(true);
    setControlError(null);

    try {
      const response = await fetch(
        `/api/copilot/conversations/${threadId}/control`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ mode }),
        },
      );

      const body = (await response.json()) as {
        detail?: string;
        mode?: "ai_active" | "human_active";
        taken_over_by_user_id?: string | null;
        taken_over_at?: string | null;
      };

      if (!response.ok || !body.mode) {
        throw new Error(
          body.detail ??
            `Changement de mode impossible (${response.status}).`,
        );
      }

      setInsight((current) =>
        current
          ? { ...current, control_mode: body.mode! }
          : current,
      );

      onControlModeChanged(
        body.mode,
        body.taken_over_by_user_id ?? null,
        body.taken_over_at ?? null,
      );
      setReloadToken((value) => value + 1);
    } catch (caughtError) {
      setControlError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de modifier le contrôle de la conversation.",
      );
    } finally {
      setChangingControl(false);
    }
  }

  return (
    <section
      aria-label="Analyse Copilote de la conversation"
      className="conversation-copilot-panel"
    >
      <header className="conversation-copilot-heading">
        <span className="conversation-copilot-icon">
          <Sparkles size={17} />
        </span>
        <div>
          <span>Copilote DentalFlow</span>
          <h3>Analyse de la conversation</h3>
        </div>
      </header>

      {loading ? (
        <div className="conversation-copilot-state">
          <LoaderCircle className="conversation-copilot-spinner" size={18} />
          Analyse en cours…
        </div>
      ) : error ? (
        <div className="conversation-copilot-state error">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      ) : insight ? (
        <div className="conversation-copilot-content">
          <div className={`conversation-copilot-handoff ${insight.control_mode}`}>
            <div>
              {insight.control_mode === "ai_active" ? (
                <Bot size={17} />
              ) : (
                <UserRound size={17} />
              )}
              <span>
                <strong>
                  {insight.control_mode === "ai_active"
                    ? "Copilote actif"
                    : insight.control_mode === "human_active"
                      ? "Prise en main humaine"
                      : insight.control_mode === "paused"
                        ? "Copilote en pause"
                        : "Conversation fermée"}
                </strong>
                <small>
                  {insight.control_mode === "ai_active"
                    ? "Les réponses automatiques sont autorisées."
                    : "Les réponses automatiques sont bloquées."}
                </small>
              </span>
            </div>

            {insight.control_mode !== "closed" && (
              <button
                type="button"
                disabled={changingControl}
                onClick={() =>
                  void changeControlMode(
                    insight.control_mode === "ai_active"
                      ? "human_active"
                      : "ai_active",
                  )
                }
              >
                {changingControl
                  ? "Mise à jour…"
                  : insight.control_mode === "ai_active"
                    ? "Prendre la main"
                    : "Réactiver le Copilote"}
              </button>
            )}

            {controlError && (
              <p role="alert">{controlError}</p>
            )}
          </div>

          <div className="conversation-copilot-patient-context">
            <div className="conversation-copilot-section-title">
              <UserRound size={15} />
              <strong>Contexte patient</strong>
            </div>

            {insight.patient_context.identified ? (
              <>
                <div className="conversation-copilot-patient-identity">
                  <strong>
                    {insight.patient_context.full_name ?? "Patient identifié"}
                  </strong>
                  <span>
                    {insight.patient_context.phone ?? insight.sender_phone}
                  </span>
                </div>

                {insight.patient_context.ai_summary && (
                  <p className="conversation-copilot-patient-summary">
                    {insight.patient_context.ai_summary}
                  </p>
                )}

                <div className="conversation-copilot-appointments">
                  <article>
                    <CalendarClock size={15} />
                    <div>
                      <span>Prochain rendez-vous</span>
                      <strong>
                        {insight.patient_context.next_appointment
                          ? new Intl.DateTimeFormat("fr-FR", {
                              dateStyle: "medium",
                              timeStyle: "short",
                            }).format(
                              new Date(
                                insight.patient_context.next_appointment.start_at,
                              ),
                            )
                          : "Aucun rendez-vous futur"}
                      </strong>
                      {insight.patient_context.next_appointment && (
                        <small>
                          {[
                            insight.patient_context.next_appointment.treatment_name,
                            insight.patient_context.next_appointment.practitioner_name,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </small>
                      )}
                    </div>
                  </article>

                  <article>
                    <HeartPulse size={15} />
                    <div>
                      <span>Dernier soin terminé</span>
                      <strong>
                        {insight.patient_context.last_completed_appointment
                          ? new Intl.DateTimeFormat("fr-FR", {
                              dateStyle: "medium",
                            }).format(
                              new Date(
                                insight.patient_context.last_completed_appointment.start_at,
                              ),
                            )
                          : "Aucun soin terminé trouvé"}
                      </strong>
                      {insight.patient_context.last_completed_appointment && (
                        <small>
                          {[
                            insight.patient_context.last_completed_appointment.treatment_name,
                            insight.patient_context.last_completed_appointment.practitioner_name,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </small>
                      )}
                    </div>
                  </article>
                </div>

                {(insight.patient_context.medical_history.length > 0 ||
                  insight.patient_context.recent_notes.length > 0) && (
                  <div className="conversation-copilot-clinical-context">
                    {insight.patient_context.medical_history.length > 0 && (
                      <div>
                        <span>
                          <HeartPulse size={14} /> Antécédents actifs
                        </span>
                        <ul>
                          {insight.patient_context.medical_history.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {insight.patient_context.recent_notes.length > 0 && (
                      <div>
                        <span>
                          <NotebookText size={14} /> Notes récentes
                        </span>
                        <ul>
                          {insight.patient_context.recent_notes.map((note) => (
                            <li key={note}>{note}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p className="conversation-copilot-muted">
                Contact non rattaché à une fiche patient.
              </p>
            )}
          </div>

          <div className="conversation-copilot-summary">
            <div className="conversation-copilot-section-title">
              <Bot size={15} />
              <strong>Résumé</strong>
            </div>
            <p>{insight.summary}</p>
          </div>

          <div className="conversation-copilot-metrics">
            <div>
              <span>Priorité</span>
              <strong
                className={`conversation-copilot-priority ${insight.priority}`}
              >
                {priorityLabels[insight.priority]}
              </strong>
            </div>
            <div>
              <span>Score</span>
              <strong>{insight.priority_score}</strong>
            </div>
            <div>
              <span>Messages</span>
              <strong>{insight.message_count}</strong>
            </div>
          </div>

          {insight.priority_reasons.length > 0 && (
            <div className="conversation-copilot-section">
              <div className="conversation-copilot-section-title">
                <ShieldCheck size={15} />
                <strong>Pourquoi cette priorité ?</strong>
              </div>
              <ul>
                {insight.priority_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="conversation-copilot-section">
            <div className="conversation-copilot-section-title">
              <Target size={15} />
              <strong>Intentions détectées</strong>
            </div>
            {insight.intents.length > 0 ? (
              <div className="conversation-copilot-tags">
                {insight.intents.map((intent) => (
                  <span key={intent}>{humanizeIntent(intent)}</span>
                ))}
              </div>
            ) : (
              <p className="conversation-copilot-muted">
                Aucune intention métier forte détectée.
              </p>
            )}
          </div>

          <div className="conversation-copilot-section">
            <div className="conversation-copilot-section-title">
              <ClipboardList size={15} />
              <strong>Actions recommandées</strong>
            </div>
            {insight.recommended_actions.length > 0 ? (
              <div className="conversation-copilot-actions">
                {insight.recommended_actions.map((action) => (
                  <article key={`${action.type}-${action.label}`}>
                    <div>
                      <CheckCircle2 size={15} />
                      <strong>{action.label}</strong>
                    </div>
                    <p>{action.description}</p>
                    {action.type === "prepare_appointment" &&
                    insight.patient_id ? (
                      <button
                        className="conversation-copilot-action-button"
                        type="button"
                        onClick={() =>
                          onPrepareAppointment(insight.patient_id as string)
                        }
                      >
                        <CalendarClock size={14} />
                        Préparer le rendez-vous
                      </button>
                    ) : null}
                    {action.type === "prepare_reschedule" &&
                    insight.patient_id &&
                    insight.patient_context.next_appointment ? (
                      <button
                        className="conversation-copilot-action-button"
                        type="button"
                        onClick={() =>
                          onPrepareReschedule(
                            insight.patient_id as string,
                            insight.patient_context.next_appointment!.id,
                          )
                        }
                      >
                        <CalendarClock size={14} />
                        Déplacer le rendez-vous
                      </button>
                    ) : action.type === "prepare_reschedule" ? (
                      <span className="conversation-copilot-action-unavailable">
                        Aucun rendez-vous futur à déplacer
                      </span>
                    ) : null}
                    {action.type === "prepare_cancellation" &&
                    insight.patient_id &&
                    insight.patient_context.next_appointment ? (
                      <button
                        className="conversation-copilot-action-button"
                        type="button"
                        disabled={
                          cancelingAppointmentId ===
                          insight.patient_context.next_appointment.id
                        }
                        onClick={() =>
                          void cancelCopilotAppointment(
                            insight.patient_context.next_appointment!,
                          )
                        }
                      >
                        <AlertTriangle size={14} />
                        {cancelingAppointmentId ===
                        insight.patient_context.next_appointment.id
                          ? "Annulation…"
                          : "Annuler le rendez-vous"}
                      </button>
                    ) : action.type === "prepare_cancellation" ? (
                      <span className="conversation-copilot-action-unavailable">
                        Aucun rendez-vous futur à annuler
                      </span>
                    ) : null}
                    {action.requires_validation && (
                      <span>Validation humaine requise</span>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <p className="conversation-copilot-muted">
                Aucune action particulière recommandée.
              </p>
            )}
          </div>

          {actionMessage ? (
            <div className="conversation-copilot-state">
              <CheckCircle2 size={16} />
              <span>{actionMessage}</span>
            </div>
          ) : null}
          {actionError ? (
            <div className="conversation-copilot-state error">
              <AlertTriangle size={16} />
              <span>{actionError}</span>
            </div>
          ) : null}

          <div className="conversation-copilot-audit">
            <div className="conversation-copilot-section-title"><History size={15} /><strong>Journal d’audit</strong></div>
            {auditLoading ? <p className="conversation-copilot-muted">Chargement du journal…</p> : auditItems.length > 0 ? (
              <ol>{auditItems.slice(0, 12).map((item) => {
                const actor = typeof item.metadata?.actor_label === "string" ? item.metadata.actor_label : item.actor_user_id ? "Utilisateur" : "Équipe clinique";
                const beforeStart = typeof item.before_data?.start_at === "string" ? item.before_data.start_at : null;
                const afterStart = typeof item.after_data?.start_at === "string" ? item.after_data.start_at : null;
                return <li key={item.id}><time>{auditDate(item.created_at)}</time><strong>{auditLabels[item.action_type] ?? item.action_type}</strong><span>{actor} · {item.result === "success" ? "Succès" : item.result}</span>{beforeStart && afterStart ? <small>{auditDate(beforeStart)} → {auditDate(afterStart)}</small> : null}</li>;
              })}</ol>
            ) : <p className="conversation-copilot-muted">Aucune action auditée pour cette conversation.</p>}
          </div>

          <div className="conversation-copilot-reply-draft">
            <div className="conversation-copilot-section-title">
              <Sparkles size={15} />
              <strong>Réponse proposée</strong>
            </div>

            <div className="conversation-copilot-draft-toolbar">
              <label>
                Ton
                <select
                  value={draftTone}
                  onChange={(event) => {
                    const tone = event.target.value as DraftTone;
                    setDraftTone(tone);
                    if (insight) setReplyDraft(buildReplyDraft(insight, tone));
                  }}
                >
                  <option value="professional">Professionnel</option>
                  <option value="warm">Chaleureux</option>
                  <option value="concise">Concis</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => insight && setReplyDraft(buildReplyDraft(insight, draftTone))}
              >
                <RefreshCw size={14} />
                {replyDraft ? "Régénérer" : "Préparer"}
              </button>
            </div>

            {replyDraft ? (
              <>
                <textarea
                  value={replyDraft}
                  onChange={(event) => setReplyDraft(event.target.value)}
                  rows={8}
                />
                <div className="conversation-copilot-draft-actions">
                  <button
                    type="button"
                    className="primary"
                    onClick={() => onUseDraft(replyDraft)}
                  >
                    <SendToBack size={14} />
                    Utiliser le brouillon
                  </button>
                  <button type="button" onClick={() => void copyDraft()}>
                    <Copy size={14} />
                    {copyLabel}
                  </button>
                </div>
                <small>Validation humaine obligatoire avant envoi.</small>
              </>
            ) : (
              <p className="conversation-copilot-muted">
                Prépare une réponse contextualisée sans l’envoyer automatiquement.
              </p>
            )}
          </div>

          <footer className="conversation-copilot-footer">
            <ShieldCheck size={14} />
            Analyse en lecture seule · aucune action exécutée automatiquement
          </footer>
        </div>
      ) : null}
    </section>
  );
}
