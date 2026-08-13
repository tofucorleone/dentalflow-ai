"use client";

import { Plus, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

type TreatmentCreateFormProps = {
  currencyLabel: string;
};

type DraftTreatmentSession = {
  id: string;
  name: string;
  duration_minutes: number;
};

export function TreatmentCreateForm({
  currencyLabel,
}: TreatmentCreateFormProps) {
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState("30");
  const [price, setPrice] = useState("0");
  const [requiresConsultation, setRequiresConsultation] =
    useState(false);
  const [active, setActive] = useState(true);

  const [draftSessions, setDraftSessions] = useState<
    DraftTreatmentSession[]
  >([]);
  const [sessionName, setSessionName] = useState("");
  const [sessionDuration, setSessionDuration] = useState("30");

  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function closeModal() {
    if (isSaving) return;

    setIsOpen(false);
    setMessage(null);
  }

  function addDraftSession() {
    const trimmedName = sessionName.trim();
    const duration = Number(sessionDuration);

    if (!trimmedName) {
      setMessage("Donnez un nom à la séance.");
      return;
    }

    if (
      !Number.isFinite(duration) ||
      duration < 1 ||
      duration > 480
    ) {
      setMessage(
        "La durée de la séance doit être comprise entre 1 et 480 minutes.",
      );
      return;
    }

    setDraftSessions((items) => [
      ...items,
      {
        id: crypto.randomUUID(),
        name: trimmedName,
        duration_minutes: duration,
      },
    ]);

    setSessionName("");
    setSessionDuration("30");
    setMessage(null);
  }

  function removeDraftSession(id: string) {
    setDraftSessions((items) =>
      items.filter((item) => item.id !== id),
    );
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);

    try {
      const response = await fetch("/api/treatments", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          duration_minutes: Number(durationMinutes),
          price: Number(price),
          requires_consultation: requiresConsultation,
          active,
        }),
      });

      const body = await response.json();

      if (!response.ok) {
        setMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de créer le soin.",
        );
        return;
      }

      if (
        draftSessions.length > 0 &&
        typeof body.id === "string"
      ) {
        for (const session of draftSessions) {
          const sessionResponse = await fetch(
            `/api/treatments/${encodeURIComponent(
              body.id,
            )}/sessions`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                name: session.name,
                duration_minutes: session.duration_minutes,
              }),
            },
          );

          const sessionBody = await sessionResponse.json();

          if (!sessionResponse.ok) {
            setMessage(
              typeof sessionBody.detail === "string"
                ? `Le soin a été créé, mais une séance n'a pas pu être créée : ${sessionBody.detail}`
                : "Le soin a été créé, mais une séance n'a pas pu être créée.",
            );
            router.refresh();
            return;
          }
        }
      }

      setName("");
      setDescription("");
      setDurationMinutes("30");
      setPrice("0");
      setRequiresConsultation(false);
      setActive(true);
      setDraftSessions([]);
      setSessionName("");
      setSessionDuration("30");
      setIsOpen(false);
      router.refresh();
    } catch {
      setMessage("Le serveur est momentanément indisponible.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <>
      <button
        className="treatment-create-trigger"
        type="button"
        onClick={() => setIsOpen(true)}
      >
        <Plus size={19} />
        Nouveau soin
      </button>

      {isOpen ? (
        <div
          className="patient-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeModal();
            }
          }}
        >
          <section
            className="patient-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="treatment-create-title"
          >
            <header className="patient-modal-header">
              <div>
                <p className="eyebrow">Soins</p>
                <h2 id="treatment-create-title">Nouveau soin</h2>
                <p>
                  Ajoutez une prestation au catalogue de la clinique.
                </p>
              </div>

              <button
                className="patient-modal-close"
                type="button"
                onClick={closeModal}
                disabled={isSaving}
                aria-label="Fermer"
              >
                <X size={20} />
              </button>
            </header>

            <form
              className="patient-create-form"
              onSubmit={handleSubmit}
            >
              <label>
                Nom du soin
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  minLength={2}
                  maxLength={120}
                  placeholder="Ex. Détartrage"
                  required
                />
              </label>

              <label>
                Description
                <textarea
                  value={description}
                  onChange={(event) =>
                    setDescription(event.target.value)
                  }
                  maxLength={1000}
                  placeholder="Description de la prestation…"
                />
              </label>

              <div className="treatment-form-grid">
                <label>
                  Durée en minutes
                  <input
                    type="number"
                    min={1}
                    max={480}
                    value={durationMinutes}
                    onChange={(event) =>
                      setDurationMinutes(event.target.value)
                    }
                    required
                  />
                </label>

                <label>
                  Prix en {currencyLabel}
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={price}
                    onChange={(event) =>
                      setPrice(event.target.value)
                    }
                    required
                  />
                </label>
              </div>

              <label className="treatment-checkbox-row">
                <input
                  type="checkbox"
                  checked={requiresConsultation}
                  onChange={(event) =>
                    setRequiresConsultation(event.target.checked)
                  }
                />
                Nécessite une consultation préalable
              </label>

              <label className="treatment-checkbox-row">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={(event) =>
                    setActive(event.target.checked)
                  }
                />
                Soin actif
              </label>

              <section className="treatment-create-sessions">
                <div className="treatment-create-sessions-heading">
                  <div>
                    <strong>Séances du soin</strong>
                    <small>
                      Optionnel — ajoutez plusieurs séances pour créer
                      un soin composé.
                    </small>
                  </div>

                  {draftSessions.length > 0 ? (
                    <span className="badge neutral">
                      {draftSessions.length} séance
                      {draftSessions.length > 1 ? "s" : ""}
                    </span>
                  ) : null}
                </div>

                {draftSessions.length > 0 ? (
                  <div className="treatment-sessions-list">
                    {draftSessions.map((session, index) => (
                      <div
                        className="treatment-session-row treatment-session-draft-row"
                        key={session.id}
                      >
                        <span className="treatment-session-position">
                          {index + 1}
                        </span>

                        <div className="treatment-session-main">
                          <strong>{session.name}</strong>
                          <small>
                            {session.duration_minutes} minutes
                          </small>
                        </div>

                        <button
                          className="treatment-session-draft-delete"
                          type="button"
                          onClick={() =>
                            removeDraftSession(session.id)
                          }
                          disabled={isSaving}
                          aria-label={`Supprimer ${session.name}`}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="treatment-sessions-empty">
                    Aucune séance ajoutée : le soin restera simple.
                  </p>
                )}

                <div className="treatment-session-add-form">
                  <input
                    value={sessionName}
                    onChange={(event) =>
                      setSessionName(event.target.value)
                    }
                    placeholder="Nom de la séance"
                    maxLength={160}
                    disabled={isSaving}
                  />

                  <input
                    type="number"
                    min={1}
                    max={480}
                    value={sessionDuration}
                    onChange={(event) =>
                      setSessionDuration(event.target.value)
                    }
                    aria-label="Durée de la séance"
                    disabled={isSaving}
                  />

                  <button
                    type="button"
                    onClick={addDraftSession}
                    disabled={isSaving}
                  >
                    <Plus size={16} />
                    Ajouter
                  </button>
                </div>
              </section>

              {message ? (
                <p className="patient-form-error">{message}</p>
              ) : null}

              <div className="patient-modal-actions">
                <button
                  className="patient-secondary-button"
                  type="button"
                  onClick={closeModal}
                  disabled={isSaving}
                >
                  Annuler
                </button>

                <button
                  className="patient-primary-button"
                  type="submit"
                  disabled={isSaving}
                >
                  {isSaving ? "Création…" : "Créer le soin"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}
