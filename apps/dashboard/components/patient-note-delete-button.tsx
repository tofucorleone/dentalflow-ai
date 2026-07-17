"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Props = {
  patientId: string;
  noteId: string;
};

export function PatientNoteDeleteButton({
  patientId,
  noteId,
}: Props) {
  const [isDeleting, setIsDeleting] = useState(false);
  const router = useRouter();

  async function handleDelete() {
    setIsDeleting(true);

    try {
      const response = await fetch(
        `/api/patients/${patientId}/notes/${noteId}`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        alert("Impossible de supprimer la note.");
        return;
      }

      router.refresh();
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleDelete}
      disabled={isDeleting}
      title="Supprimer la note"
      aria-label="Supprimer la note"
    >
      {isDeleting ? "…" : "🗑"}
    </button>
  );
}
