"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type TaskActionProps = {
  taskId: string;
  taskType: string;
  patientId: string | null;
  appointmentId: string | null;
  draftId: string | null;
  draftMessage: string | null;
  reasons: string[];
  score: number;
  status: TaskStatus;
};

type TaskStatus =
  | "open"
  | "prepared"
  | "completed"
  | "dismissed"
  | "snoozed";

type TaskUpdate = {
  status: TaskStatus;
  snoozed_until?: string | null;
  assign_to_me?: boolean;
};

export function TaskActions({
  taskId,
  taskType,
  patientId,
  appointmentId,
  draftId,
  draftMessage,
  reasons,
  score,
  status,
}: TaskActionProps) {
  const router = useRouter();
  const [loadingAction, setLoadingAction] =
    useState<string | null>(null);

  const [isEditingDraft, setIsEditingDraft] =
    useState(false);

  const [editedDraftMessage, setEditedDraftMessage] =
    useState(draftMessage ?? "");

  async function updateTask(
    action: string,
    payload: TaskUpdate,
  ) {
    setLoadingAction(action);

    try {
      const response = await fetch(
        `/api/copilot/tasks/${encodeURIComponent(taskId)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      if (!response.ok) {
        const detail = await response.text();

        throw new Error(
          `Erreur ${response.status}: ${detail}`,
        );
      }

      router.refresh();
    } catch (error) {
      console.error(error);
      alert(
        "Impossible de mettre à jour la tâche.",
      );
    } finally {
      setLoadingAction(null);
    }
  }

  async function prepareRecallMessage() {
    if (
      taskType !== "recall" ||
      !patientId ||
      !draftMessage
    ) {
      return;
    }

    setLoadingAction("prepare");

    try {
      const response = await fetch(
        "/api/copilot/recall/drafts",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            patient_id: patientId,
            appointment_id: appointmentId,
            message: draftMessage,
            candidate_score: score,
            match_level: "preventive",
            reasons,
          }),
        },
      );

      if (!response.ok) {
        const detail = await response.text();

        throw new Error(
          `Erreur ${response.status}: ${detail}`,
        );
      }

      const taskResponse = await fetch(
        `/api/copilot/tasks/${encodeURIComponent(taskId)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: "prepared",
          }),
        },
      );

      if (!taskResponse.ok) {
        const detail = await taskResponse.text();

        throw new Error(
          `Erreur ${taskResponse.status}: ${detail}`,
        );
      }

      router.refresh();
    } catch (error) {
      console.error(error);

      alert(
        "Impossible de préparer le message.",
      );
    } finally {
      setLoadingAction(null);
    }
  }

  async function prepareAppointmentMessage() {
    if (
      (
        taskType !== "pending_confirmation" &&
        taskType !== "no_show"
      ) ||
      !patientId ||
      !appointmentId ||
      !draftMessage
    ) {
      return;
    }

    setLoadingAction("prepare-appointment");

    try {
      const response = await fetch(
        "/api/copilot/appointment-message-drafts",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            patient_id: patientId,
            appointment_id: appointmentId,
            message_kind: taskType,
            message: draftMessage,
          }),
        },
      );

      if (!response.ok) {
        const detail = await response.text();

        throw new Error(
          `Erreur ${response.status}: ${detail}`,
        );
      }

      const taskResponse = await fetch(
        `/api/copilot/tasks/${encodeURIComponent(taskId)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: "prepared",
          }),
        },
      );

      if (!taskResponse.ok) {
        const detail = await taskResponse.text();

        throw new Error(
          `Erreur ${taskResponse.status}: ${detail}`,
        );
      }

      router.refresh();
    } catch (error) {
      console.error(error);

      alert(
        "Impossible de préparer le message.",
      );
    } finally {
      setLoadingAction(null);
    }
  }


  async function sendAppointmentMessage() {
    if (
      (
        taskType !== "pending_confirmation" &&
        taskType !== "no_show"
      ) ||
      !patientId ||
      !appointmentId ||
      !draftId ||
      !draftMessage
    ) {
      return;
    }

    const confirmed = window.confirm(
      "Valider et envoyer ce message WhatsApp au patient ?",
    );

    if (!confirmed) {
      return;
    }

    setLoadingAction("send-appointment");

    try {
      const response = await fetch(
        "/api/copilot/appointment-message-drafts/send",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            draft_id: draftId,
            patient_id: patientId,
            appointment_id: appointmentId,
            message_kind: taskType,
            message: draftMessage,
          }),
        },
      );

      const text = await response.text();

      if (!response.ok) {
        let detail = text;

        try {
          const payload = JSON.parse(text);

          if (
            payload &&
            typeof payload === "object" &&
            "detail" in payload
          ) {
            detail = String(payload.detail);
          }
        } catch {
          // Réponse non JSON : conserver le texte brut.
        }

        throw new Error(
          detail || `Erreur ${response.status}`,
        );
      }

      router.refresh();
    } catch (error) {
      console.error(error);

      alert(
        error instanceof Error
          ? error.message
          : "Impossible d'envoyer le message WhatsApp.",
      );
    } finally {
      setLoadingAction(null);
    }
  }


  async function sendRecallMessage() {
    if (
      taskType !== "recall" ||
      !patientId ||
      !draftId ||
      !draftMessage
    ) {
      return;
    }

    const confirmed = window.confirm(
      "Valider et envoyer ce message WhatsApp au patient ?",
    );

    if (!confirmed) {
      return;
    }

    setLoadingAction("send-recall");

    try {
      const response = await fetch(
        "/api/copilot/recall/send",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            draft_id: draftId,
            patient_id: patientId,
            message: draftMessage,
          }),
        },
      );

      const text = await response.text();

      if (!response.ok) {
        let detail = text;

        try {
          const payload = JSON.parse(text);

          if (
            payload &&
            typeof payload === "object" &&
            "detail" in payload
          ) {
            detail = String(payload.detail);
          }
        } catch {
          // Réponse non JSON : conserver le texte brut.
        }

        throw new Error(
          detail || `Erreur ${response.status}`,
        );
      }

      router.refresh();
    } catch (error) {
      console.error(error);

      alert(
        error instanceof Error
          ? error.message
          : "Impossible d'envoyer le message WhatsApp.",
      );
    } finally {
      setLoadingAction(null);
    }
  }


  async function saveRecallDraft() {
    const message = editedDraftMessage.trim();

    if (!draftId || !message) {
      return;
    }

    setLoadingAction("save-draft");

    try {
      const response = await fetch(
        `/api/copilot/recall/drafts/${encodeURIComponent(draftId)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message,
          }),
        },
      );

      if (!response.ok) {
        const detail = await response.text();

        throw new Error(
          `Erreur ${response.status}: ${detail}`,
        );
      }

      setEditedDraftMessage(message);
      setIsEditingDraft(false);
      router.refresh();
    } catch (error) {
      console.error(error);

      alert(
        "Impossible de modifier le brouillon.",
      );
    } finally {
      setLoadingAction(null);
    }
  }

  function cancelRecallDraftEdit() {
    setEditedDraftMessage(draftMessage ?? "");
    setIsEditingDraft(false);
  }

  function snoozeUntilTomorrow() {
    const tomorrow = new Date();

    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);

    void updateTask("snooze", {
      status: "snoozed",
      snoozed_until: tomorrow.toISOString(),
    });
  }

  const busy = loadingAction !== null;

  return (
    <div className="tasks-state-actions">
      {taskType === "recall" &&
      patientId &&
      draftMessage ? (
        status === "prepared" ? (
          <div className="copilot-overdue-draft-content">
            <strong>Brouillon préparé</strong>

            {isEditingDraft ? (
              <textarea
                className="tasks-draft-editor"
                disabled={busy}
                maxLength={4000}
                onChange={(event) =>
                  setEditedDraftMessage(
                    event.target.value,
                  )
                }
                value={editedDraftMessage}
              />
            ) : (
              <pre>{draftMessage}</pre>
            )}

            <div className="tasks-draft-edit-actions">
              {isEditingDraft ? (
                <>
                  <button
                    className="tasks-secondary-button"
                    disabled={
                      busy ||
                      !editedDraftMessage.trim()
                    }
                    onClick={() =>
                      void saveRecallDraft()
                    }
                    type="button"
                  >
                    {loadingAction === "save-draft"
                      ? "..."
                      : "Enregistrer"}
                  </button>

                  <button
                    className="tasks-dismiss-button"
                    disabled={busy}
                    onClick={cancelRecallDraftEdit}
                    type="button"
                  >
                    Annuler
                  </button>
                </>
              ) : draftId ? (
                <>
                  <button
                    className="tasks-secondary-button"
                    disabled={busy}
                    onClick={() => {
                      setEditedDraftMessage(
                        draftMessage,
                      );
                      setIsEditingDraft(true);
                    }}
                    type="button"
                  >
                    Modifier
                  </button>

                  <button
                    className="tasks-complete-button"
                    disabled={busy}
                    onClick={() =>
                      void sendRecallMessage()
                    }
                    type="button"
                  >
                    {loadingAction === "send-recall"
                      ? "Envoi..."
                      : "Valider et envoyer WhatsApp"}
                  </button>
                </>
              ) : null}
            </div>

            <span className="copilot-draft-lock">
              Aucun envoi automatique
            </span>
          </div>
        ) : (
          <button
            className="tasks-secondary-button"
            disabled={busy}
            onClick={() =>
              void prepareRecallMessage()
            }
            type="button"
          >
            {loadingAction === "prepare"
              ? "..."
              : "Préparer le message"}
          </button>
        )
      ) : null}

      {(taskType === "pending_confirmation" ||
        taskType === "no_show") &&
      patientId &&
      appointmentId &&
      draftMessage ? (
        status === "prepared" && draftId ? (
          <div className="copilot-overdue-draft-content">
            <pre>{draftMessage}</pre>

            <div className="copilot-overdue-draft-footer">
              <span className="copilot-draft-lock">
                Aucun envoi automatique
              </span>

              <button
                className="tasks-complete-button"
                disabled={busy}
                onClick={() =>
                  void sendAppointmentMessage()
                }
                type="button"
              >
                {loadingAction === "send-appointment"
                  ? "Envoi..."
                  : "Valider et envoyer WhatsApp"}
              </button>
            </div>
          </div>
        ) : status !== "prepared" ? (
          <button
            className="tasks-secondary-button"
            disabled={busy}
            onClick={() =>
              void prepareAppointmentMessage()
            }
            type="button"
          >
            {loadingAction === "prepare-appointment"
              ? "..."
              : "Préparer le message"}
          </button>
        ) : null
      ) : null}

      <button
        className="tasks-complete-button"
        disabled={busy || isEditingDraft}
        onClick={() =>
          void updateTask("complete", {
            status: "completed",
          })
        }
        type="button"
      >
        {loadingAction === "complete"
          ? "..."
          : "Terminer"}
      </button>

      <button
        className="tasks-secondary-button"
        disabled={busy || isEditingDraft}
        onClick={snoozeUntilTomorrow}
        type="button"
      >
        {loadingAction === "snooze"
          ? "..."
          : "Reporter"}
      </button>

      <button
        className="tasks-secondary-button"
        disabled={busy || isEditingDraft}
        onClick={() =>
          void updateTask("assign", {
            status: "open",
            assign_to_me: true,
          })
        }
        type="button"
      >
        {loadingAction === "assign"
          ? "..."
          : "Me l’attribuer"}
      </button>

      <button
        className="tasks-dismiss-button"
        disabled={busy || isEditingDraft}
        onClick={() =>
          void updateTask("dismiss", {
            status: "dismissed",
          })
        }
        type="button"
      >
        {loadingAction === "dismiss"
          ? "..."
          : "Ignorer"}
      </button>
    </div>
  );
}
