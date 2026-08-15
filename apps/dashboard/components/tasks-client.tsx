"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type TaskActionProps = {
  taskId: string;
  taskType: string;
  patientId: string | null;
  appointmentId: string | null;
  draftMessage: string | null;
  reasons: string[];
  score: number;
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
  draftMessage,
  reasons,
  score,
}: TaskActionProps) {
  const router = useRouter();
  const [loadingAction, setLoadingAction] =
    useState<string | null>(null);

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
      ) : null}

      <button
        className="tasks-complete-button"
        disabled={busy}
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
        disabled={busy}
        onClick={snoozeUntilTomorrow}
        type="button"
      >
        {loadingAction === "snooze"
          ? "..."
          : "Reporter"}
      </button>

      <button
        className="tasks-secondary-button"
        disabled={busy}
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
        disabled={busy}
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
