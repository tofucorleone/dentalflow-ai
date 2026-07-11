"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export function PatientNoteForm({ patientId }: { patientId: string }) {
  const [note, setNote] = useState("");
  const [author, setAuthor] = useState("Secrétariat");
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setMessage(null);

    startTransition(async () => {
      const response = await fetch(`/api/patients/${patientId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author_name: author, note }),
      });

      const body = await response.json();
      if (!response.ok) {
        setMessage(typeof body.detail === "string" ? body.detail : "Impossible d'ajouter la note.");
        return;
      }

      setNote("");
      setMessage("Note ajoutée.");
      router.refresh();
    });
  }

  return (
    <form className="note-form" onSubmit={submit}>
      <input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Auteur" />
      <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ajouter une note administrative…" required />
      <button disabled={isPending} type="submit">
        {isPending ? "Enregistrement…" : "Ajouter la note"}
      </button>
      {message && <p>{message}</p>}
    </form>
  );
}
