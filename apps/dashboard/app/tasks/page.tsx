import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  ListTodo,
  Sparkles,
} from "lucide-react";

import { backendFetch } from "@/lib/server-api";
import { TaskActions } from "@/components/tasks-client";

type CopilotTask = {
  id: string;
  type:
    | "recall"
    | "released_slot"
    | "late_active"
    | "pending_confirmation"
    | "no_show";
  priority: "high" | "medium" | "low";
  score: number;
  title: string;
  description: string;
  recommended_action: string;
  patient_id: string | null;
  appointment_id: string | null;
  draft_id: string | null;
  draft_message: string | null;
  reasons: string[];
  status:
    | "open"
    | "prepared"
    | "completed"
    | "dismissed"
    | "snoozed";
  assigned_user_id: string | null;
  snoozed_until: string | null;
  completed_at: string | null;
  confirmation_status:
    | "sent"
    | "confirmed"
    | null;
  requires_validation: boolean;
  actions: Array<{
    type: string;
    label: string;
    href?: string | null;
  }>;
};

async function getTasks(): Promise<CopilotTask[]> {
  const response = await backendFetch("/copilot/tasks", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `Impossible de charger les tâches (${response.status}).`,
    );
  }

  return response.json() as Promise<CopilotTask[]>;
}

function priorityLabel(priority: CopilotTask["priority"]) {
  if (priority === "high") return "Urgent";
  if (priority === "medium") return "Haute";
  return "Normale";
}

function confirmationStatusLabel(
  task: CopilotTask,
): string | null {
  if (task.type !== "pending_confirmation") {
    return null;
  }

  if (task.confirmation_status === "confirmed") {
    return "Rendez-vous confirmé par le patient";
  }

  if (task.confirmation_status === "sent") {
    return "Message envoyé — en attente de confirmation";
  }

  return null;
}

export default async function TasksPage() {
  const tasks = await getTasks();

  const openTasks = tasks.filter(
    (task) => task.status === "open" || task.status === "prepared",
  );

  const completedTasks = tasks.filter(
    (task) => task.status === "completed",
  );

  return (
    <div className="tasks-page">
      <section className="tasks-hero">
        <div>
          <p className="tasks-kicker">
            <Sparkles size={16} />
            Copilote DentalFlow
          </p>

          <h1>Tâches IA</h1>

          <p>
            Actions opérationnelles proposées automatiquement par le
            Copilote.
          </p>
        </div>
      </section>

      <section className="tasks-summary-grid">
        <article>
          <ListTodo size={20} />
          <span>À faire</span>
          <strong>{openTasks.length}</strong>
        </article>

        <article>
          <Clock3 size={20} />
          <span>Priorité haute</span>
          <strong>
            {
              openTasks.filter(
                (task) => task.priority === "high",
              ).length
            }
          </strong>
        </article>

        <article>
          <CheckCircle2 size={20} />
          <span>Terminées</span>
          <strong>{completedTasks.length}</strong>
        </article>
      </section>

      {openTasks.length === 0 ? (
        <section className="tasks-empty-state">
          <ListTodo size={34} />
          <h2>Aucune tâche à traiter</h2>
          <p>
            Le Copilote n’a actuellement aucune action opérationnelle à
            recommander.
          </p>
        </section>
      ) : (
        <section className="tasks-list">
          {openTasks.map((task) => {
            const navigationAction = task.actions.find(
              (action) =>
                action.type === "navigate" && action.href,
            );

            return (
              <article
                className={`tasks-item priority-${task.priority}`}
                key={task.id}
              >
                <div className="tasks-item-priority">
                  <AlertCircle size={18} />
                  <span>{priorityLabel(task.priority)}</span>
                </div>

                <div className="tasks-item-content">
                  <h2>{task.title}</h2>

                  {task.description ? (
                    <p>{task.description}</p>
                  ) : null}

                  <div className="tasks-item-meta">
                    <span>Score {task.score}</span>
                    <span>Créé par le Copilote</span>

                    {confirmationStatusLabel(task) ? (
                      <span>
                        {confirmationStatusLabel(task)}
                      </span>
                    ) : null}

                    {task.assigned_user_id ? (
                      <span>Attribuée</span>
                    ) : null}

                    {task.snoozed_until ? (
                      <span>
                        Reportée jusqu’au{" "}
                        {new Date(
                          task.snoozed_until,
                        ).toLocaleString("fr-FR")}
                      </span>
                    ) : null}

                    {task.requires_validation ? (
                      <span>Validation requise</span>
                    ) : null}
                  </div>
                </div>

                <div className="tasks-item-actions">
                  {navigationAction?.href ? (
                    <Link
                      className="tasks-item-action"
                      href={navigationAction.href}
                    >
                      {navigationAction.label}
                    </Link>
                  ) : null}

                  <TaskActions
                    appointmentId={task.appointment_id}
                    draftId={task.draft_id}
                    draftMessage={task.draft_message}
                    status={task.status}
                    patientId={task.patient_id}
                    reasons={task.reasons}
                    score={task.score}
                    taskId={task.id}
                    taskType={task.type}
                  />
                </div>
              </article>
            );
          })}
        </section>
      )}

      {completedTasks.length > 0 ? (
        <section className="tasks-list">
          {completedTasks.map((task) => {
            const navigationAction = task.actions.find(
              (action) =>
                action.type === "navigate" &&
                action.href,
            );

            return (
              <article
                className={`tasks-item priority-${task.priority}`}
                key={task.id}
              >
                <div className="tasks-item-priority">
                  <CheckCircle2 size={18} />
                  <span>Terminée</span>
                </div>

                <div className="tasks-item-content">
                  <h2>{task.title}</h2>

                  {task.description ? (
                    <p>{task.description}</p>
                  ) : null}

                  <div className="tasks-item-meta">
                    {confirmationStatusLabel(task) ? (
                      <span>
                        {confirmationStatusLabel(task)}
                      </span>
                    ) : (
                      <span>Tâche terminée</span>
                    )}

                    {task.completed_at ? (
                      <span>
                        Terminée le{" "}
                        {new Date(
                          task.completed_at,
                        ).toLocaleString("fr-FR")}
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="tasks-item-actions">
                  {navigationAction?.href ? (
                    <Link
                      className="tasks-item-action"
                      href={navigationAction.href}
                    >
                      {navigationAction.label}
                    </Link>
                  ) : null}
                </div>
              </article>
            );
          })}
        </section>
      ) : null}
    </div>
  );
}
