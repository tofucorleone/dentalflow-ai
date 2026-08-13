"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type TaskActionProps = {
  taskId: string;
};

export function TaskCompleteButton({
  taskId,
}: TaskActionProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function completeTask() {
    setLoading(true);

    try {
      const response = await fetch(
        `/api/copilot/tasks/${encodeURIComponent(taskId)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: "completed",
          }),
        },
      );

      if (!response.ok) {
        throw new Error(
          `Erreur ${response.status}`,
        );
      }

      router.refresh();
    } catch (error) {
      console.error(error);
      alert(
        "Impossible de terminer la tâche.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      className="tasks-complete-button"
      disabled={loading}
      onClick={completeTask}
      type="button"
    >
      {loading ? "..." : "Terminer"}
    </button>
  );
}
