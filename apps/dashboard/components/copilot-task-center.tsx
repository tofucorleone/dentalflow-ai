"use client";

import { useRouter } from "next/navigation";

import {
  CalendarClock,
  Check,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Play,
  RotateCcw,
  UserRoundSearch,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { CopilotTask } from "@/lib/server-api";


type Props = {
  tasks: CopilotTask[];
};

type TaskFilter =
  | "all"
  | CopilotTask["type"];

type LocalTaskStatus =
  | "open"
  | "in_progress"
  | "completed"
  | "dismissed";

type TaskStatusMap = Record<
  string,
  LocalTaskStatus
>;


const filters: {
  value: TaskFilter;
  label: string;
}[] = [
  {
    value: "all",
    label: "Toutes",
  },
  {
    value: "recall",
    label: "Rappels",
  },
  {
    value: "released_slot",
    label: "Créneaux",
  },
  {
    value: "late_active",
    label: "Retards",
  },
  {
    value: "pending_confirmation",
    label: "Confirmations",
  },
  {
    value: "no_show",
    label: "Absences",
  },
  {
    value: "conversation_reply",
    label: "Conversations",
  },
];


function initialTaskStatus(
  task: CopilotTask,
): LocalTaskStatus {
  if (task.status === "completed") {
    return "completed";
  }

  if (task.status === "dismissed") {
    return "dismissed";
  }

  if (task.status === "prepared") {
    return "in_progress";
  }

  return "open";
}


function createInitialStatusMap(
  tasks: CopilotTask[],
): TaskStatusMap {
  return Object.fromEntries(
    tasks.map((task) => [
      task.id,
      initialTaskStatus(task),
    ]),
  );
}


function taskTypeLabel(
  type: CopilotTask["type"],
): string {
  const labels: Record<
    CopilotTask["type"],
    string
  > = {
    recall: "Rappel patient",
    released_slot: "Créneau libéré",
    late_active: "Rendez-vous en retard",
    pending_confirmation: "Confirmation",
    no_show: "Absence patient",
    conversation_reply: "Conversation à traiter",
  };

  return labels[type];
}


function taskIcon(
  type: CopilotTask["type"],
) {
  if (type === "recall") {
    return <UserRoundSearch size={20} />;
  }

  if (type === "released_slot") {
    return <CalendarClock size={20} />;
  }

  if (type === "late_active") {
    return <Clock3 size={20} />;
  }

  if (type === "pending_confirmation") {
    return <CheckCircle2 size={20} />;
  }

  return <CircleAlert size={20} />;
}


function priorityLabel(
  priority: CopilotTask["priority"],
): string {
  if (priority === "high") {
    return "Priorité haute";
  }

  if (priority === "medium") {
    return "Priorité moyenne";
  }

  return "Priorité basse";
}


function statusLabel(
  status: LocalTaskStatus,
): string {
  const labels: Record<
    LocalTaskStatus,
    string
  > = {
    open: "Ouverte",
    in_progress: "En cours",
    completed: "Terminée",
    dismissed: "Ignorée",
  };

  return labels[status];
}


export function CopilotTaskCenter({
  tasks,
}: Props) {
  const router = useRouter();

  const [activeFilter, setActiveFilter] =
    useState<TaskFilter>("all");

  const [taskStatuses, setTaskStatuses] =
    useState<TaskStatusMap>(() =>
      createInitialStatusMap(tasks),
    );

  useEffect(() => {
    const eventSource = new EventSource(
      "/api/conversations/events",
    );

    const refreshTasks = () => {
      router.refresh();
    };

    const events = [
      "conversation.message.received",
      "conversation.message.sent",
      "conversation.thread.updated",
      "conversation.control.updated",
      "copilot.task.created",
      "copilot.task.updated",
      "copilot.task.completed",
    ];

    for (const eventName of events) {
      eventSource.addEventListener(
        eventName,
        refreshTasks,
      );
    }

    return () => {
      for (const eventName of events) {
        eventSource.removeEventListener(
          eventName,
          refreshTasks,
        );
      }

      eventSource.close();
    };
  }, [router]);

  const tasksWithLocalStatus = useMemo(
    () =>
      tasks.map((task) => ({
        ...task,
        localStatus:
          taskStatuses[task.id] ??
          initialTaskStatus(task),
      })),
    [taskStatuses, tasks],
  );

  const visibleTasks = useMemo(
    () =>
      activeFilter === "all"
        ? tasksWithLocalStatus
        : tasksWithLocalStatus.filter(
            (task) =>
              task.type === activeFilter,
          ),
    [activeFilter, tasksWithLocalStatus],
  );

  async function updateTaskStatus(
    taskId: string,
    status: LocalTaskStatus,
  ): Promise<void> {
    const previousStatus =
      taskStatuses[taskId] ?? "open";

    setTaskStatuses((current) => ({
      ...current,
      [taskId]: status,
    }));

    const persistentStatus =
      status === "in_progress"
        ? "open"
        : status;

    try {
      const response = await fetch(
        `/api/copilot/tasks/${encodeURIComponent(taskId)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: persistentStatus,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(
          `Erreur API ${response.status}`,
        );
      }

      router.refresh();
    } catch (error) {
      console.error(error);

      setTaskStatuses((current) => ({
        ...current,
        [taskId]: previousStatus,
      }));

      alert(
        "Impossible de modifier cette tâche.",
      );
    }
  }

  function filterCount(
    filter: TaskFilter,
  ): number {
    if (filter === "all") {
      return tasksWithLocalStatus.length;
    }

    return tasksWithLocalStatus.filter(
      (task) => task.type === filter,
    ).length;
  }

  const statusCounts = useMemo(
    () => ({
      open: tasksWithLocalStatus.filter(
        (task) => task.localStatus === "open",
      ).length,
      inProgress:
        tasksWithLocalStatus.filter(
          (task) =>
            task.localStatus === "in_progress",
        ).length,
      completed:
        tasksWithLocalStatus.filter(
          (task) =>
            task.localStatus === "completed",
        ).length,
      dismissed:
        tasksWithLocalStatus.filter(
          (task) =>
            task.localStatus === "dismissed",
        ).length,
    }),
    [tasksWithLocalStatus],
  );

  return (
    <section className="copilot-task-center">
      <div className="copilot-task-center-heading">
        <div>
          <span>Centre opérationnel</span>
          <h2>Tâches Copilote</h2>
          <p>
            Recommandations unifiées, classées par
            priorité et score.
          </p>
        </div>

        <strong>{visibleTasks.length}</strong>
      </div>

      <div className="copilot-task-status-summary">
        <span>
          Ouvertes <strong>{statusCounts.open}</strong>
        </span>

        <span>
          En cours{" "}
          <strong>{statusCounts.inProgress}</strong>
        </span>

        <span>
          Terminées{" "}
          <strong>{statusCounts.completed}</strong>
        </span>

        <span>
          Ignorées{" "}
          <strong>{statusCounts.dismissed}</strong>
        </span>
      </div>

      <div
        aria-label="Filtres des tâches Copilote"
        className="copilot-task-filters"
        role="group"
      >
        {filters.map((filter) => {
          const count = filterCount(
            filter.value,
          );

          return (
            <button
              aria-pressed={
                activeFilter === filter.value
              }
              className={`copilot-task-filter ${
                activeFilter === filter.value
                  ? "active"
                  : ""
              }`}
              key={filter.value}
              onClick={() =>
                setActiveFilter(filter.value)
              }
              type="button"
            >
              <span>{filter.label}</span>
              <strong>{count}</strong>
            </button>
          );
        })}
      </div>

      {visibleTasks.length === 0 ? (
        <div className="copilot-task-empty">
          Aucune tâche dans cette catégorie.
        </div>
      ) : (
        <div className="copilot-task-list">
          {visibleTasks.map((task) => (
            <article
              className={[
                "copilot-task-card",
                task.priority,
                `status-${task.localStatus}`,
              ].join(" ")}
              key={task.id}
            >
              <div className="copilot-task-icon">
                {task.localStatus ===
                "completed" ? (
                  <Check size={20} />
                ) : (
                  taskIcon(task.type)
                )}
              </div>

              <div className="copilot-task-main">
                <div className="copilot-task-meta">
                  <span className="copilot-task-type">
                    {taskTypeLabel(task.type)}
                  </span>

                  <span
                    className={`copilot-task-priority ${task.priority}`}
                  >
                    {priorityLabel(task.priority)}
                  </span>

                  <span className="copilot-task-score">
                    Score {task.score}
                  </span>

                  <span
                    className={`copilot-task-status status-${task.localStatus}`}
                  >
                    {statusLabel(
                      task.localStatus,
                    )}
                  </span>
                </div>

                <h3>{task.title}</h3>
                <p>{task.description}</p>

                <div className="copilot-task-actions">
                  {task.actions.map((action) => (
                    <Link
                      className="copilot-task-link"
                      href={action.href}
                      key={`${task.id}-${action.href}-${action.label}`}
                    >
                      {action.label}
                    </Link>
                  ))}

                  {task.localStatus === "open" ? (
                    <>
                      <button
                        className="copilot-task-workflow-button start"
                        onClick={() =>
                          updateTaskStatus(
                            task.id,
                            "in_progress",
                          )
                        }
                        type="button"
                      >
                        <Play size={15} />
                        Commencer
                      </button>

                      <button
                        className="copilot-task-workflow-button dismiss"
                        onClick={() =>
                          updateTaskStatus(
                            task.id,
                            "dismissed",
                          )
                        }
                        type="button"
                      >
                        <X size={15} />
                        Ignorer
                      </button>
                    </>
                  ) : null}

                  {task.localStatus ===
                  "in_progress" ? (
                    <>
                      <button
                        className="copilot-task-workflow-button complete"
                        onClick={() =>
                          updateTaskStatus(
                            task.id,
                            "completed",
                          )
                        }
                        type="button"
                      >
                        <Check size={15} />
                        Terminer
                      </button>

                      <button
                        className="copilot-task-workflow-button dismiss"
                        onClick={() =>
                          updateTaskStatus(
                            task.id,
                            "dismissed",
                          )
                        }
                        type="button"
                      >
                        <X size={15} />
                        Ignorer
                      </button>
                    </>
                  ) : null}

                  {task.localStatus ===
                    "completed" ||
                  task.localStatus ===
                    "dismissed" ? (
                    <button
                      className="copilot-task-workflow-button reopen"
                      onClick={() =>
                        updateTaskStatus(
                          task.id,
                          "open",
                        )
                      }
                      type="button"
                    >
                      <RotateCcw size={15} />
                      Réouvrir
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <p className="copilot-task-local-notice">
        Les changements d’état sont locaux à cette
        page et ne sont pas encore enregistrés en base.
      </p>
    </section>
  );
}
