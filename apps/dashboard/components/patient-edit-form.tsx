"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Props = {
  patient: {
    id: string;
    full_name: string | null;
    phone: string;
    email: string | null;
    administrative_notes: string | null;
  };
};

export function PatientEditForm({ patient }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [fullName, setFullName] = useState(patient.full_name ?? "");
  const [phone, setPhone] = useState(patient.phone);
  const [email, setEmail] = useState(patient.email ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const router = useRouter();

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);

    try {
      const response = await fetch(
        `/api/patients/${patient.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            full_name: fullName || null,
            phone,
            email: email || null,
          }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de modifier le patient.",
        );
        return;
      }

      setIsOpen(false);
      router.refresh();
    } finally {
      setIsSaving(false);
    }
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
      >
        Modifier le patient
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        display: "grid",
        gap: "12px",
        marginTop: "18px",
      }}
    >
      <label>
        Nom complet
        <input
          value={fullName}
          onChange={(event) =>
            setFullName(event.target.value)
          }
        />
      </label>

      <label>
        Téléphone
        <input
          value={phone}
          onChange={(event) =>
            setPhone(event.target.value)
          }
          required
        />
      </label>

      <label>
        E-mail
        <input
          type="email"
          value={email}
          onChange={(event) =>
            setEmail(event.target.value)
          }
        />
      </label>

      {message && <p>{message}</p>}

      <div
        style={{
          display: "flex",
          gap: "10px",
        }}
      >
        <button
          type="submit"
          disabled={isSaving}
        >
          {isSaving ? "Enregistrement…" : "Enregistrer"}
        </button>

        <button
          type="button"
          onClick={() => setIsOpen(false)}
          disabled={isSaving}
        >
          Annuler
        </button>
      </div>
    </form>
  );
}
