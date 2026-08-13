"use client";

import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import type { TreatmentSession } from "@/lib/api";

type Props = {
  treatmentId: string;
};

export function TreatmentSessionsManager({
  treatmentId,
}: Props) {
  const [sessions, setSessions] = useState<TreatmentSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);

  const [name, setName] = useState("");
  const [durationMinutes, setDurationMinutes] = useState("30");
  const [message, setMessage] = useState<string | null>(null);

  async function loadSessions() {
    setIsLoading(true);
    setMessage(null);

    try {
      const response = await fetch(
        `/api/treatments/${encodeURIComponent(
          treatmentId,
        )}/sessions`,
        {
          cache: "no-store",
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de charger les séances.",
        );
        return;
      }

      setSessions(body);
    } catch {
      setMessage("Le serveur est momentanément indisponible.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadSessions();
  }, [treatmentId]);

  async function addSession() {
    const trimmedName = name.trim();

    if (!trimmedName) {
      setMessage("Le nom de la séance est obligatoire.");
      return;
    }

    setIsAdding(true);
    setMessage(null);

    try {
      const response = await fetch(
        `/api/treatments/${encodeURIComponent(
          treatmentId,
        )}/sessions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: trimmedName,
            duration_minutes: Number(durationMinutes),
          }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible d'ajouter la séance.",
        );
        return;
      }

      setName("");
      setDurationMinutes("30");

      await loadSessions();
    } catch {
      setMessage("Le serveur est momentanément indisponible.");
    } finally {
      setIsAdding(false);
    }
  }

  return (
    <div className="treatment-sessions-manager">
      <div className="treatment-sessions-heading">
        <div>
          <strong>
            {sessions.length > 0
              ? `${sessions.length} séance${
                  sessions.length > 1 ? "s" : ""
                }`
              : "Soin simple"}
          </strong>

          <small>
            {sessions.length > 0
              ? "Protocole composé"
              : "Ajoutez des séances pour créer un soin composé."}
          </small>
        </div>
      </div>

      {isLoading ? (
        <p className="treatment-sessions-empty">
          Chargement des séances…
        </p>
      ) : sessions.length > 0 ? (
        <div className="treatment-sessions-list">
          {sessions.map((session) => (
            <div
              className="treatment-session-row"
              key={session.id}
            >
              <span className="treatment-session-position">
                {session.position}
              </span>

              <div className="treatment-session-main">
                <strong>{session.name}</strong>
                <small>
                  {session.duration_minutes} minutes
                </small>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="treatment-session-add-form">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Nom de la séance"
          maxLength={160}
        />

        <input
          type="number"
          min={1}
          max={480}
          value={durationMinutes}
          onChange={(event) =>
            setDurationMinutes(event.target.value)
          }
          aria-label="Durée de la séance"
        />

        <button
          type="button"
          onClick={() => void addSession()}
          disabled={isAdding}
        >
          <Plus size={16} />
          {isAdding ? "Ajout…" : "Ajouter"}
        </button>
      </div>

      {message ? (
        <p className="patient-form-error">{message}</p>
      ) : null}
    </div>
  );
}
