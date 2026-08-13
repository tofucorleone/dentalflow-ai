"use client";

import {
  AlertTriangle,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TreatmentSessionsManager } from "@/components/treatment-sessions-manager";

type TreatmentCardActionsProps = {
  currencyLabel: string;
  treatment: {
    id: string;
    name: string;
    description: string | null;
    duration_minutes: number;
    price: number;
    active: boolean;
    requires_consultation?: boolean;
  };
};

export function TreatmentCardActions({
  treatment,
  currencyLabel,
}: TreatmentCardActionsProps) {
  const router = useRouter();

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const [name, setName] = useState(treatment.name);
  const [description, setDescription] = useState(
    treatment.description ?? "",
  );
  const [durationMinutes, setDurationMinutes] = useState(
    String(treatment.duration_minutes),
  );
  const [price, setPrice] = useState(String(treatment.price));
  const [requiresConsultation, setRequiresConsultation] =
    useState(treatment.requires_consultation ?? false);
  const [active, setActive] = useState(treatment.active);

  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editMessage, setEditMessage] =
    useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] =
    useState<string | null>(null);

  function closeEditModal() {
    if (isSaving) return;

    setIsEditOpen(false);
    setEditMessage(null);
  }

  function closeDeleteModal() {
    if (isDeleting) return;

    setIsDeleteOpen(false);
    setDeleteMessage(null);
  }

  async function handleUpdate(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setIsSaving(true);
    setEditMessage(null);

    try {
      const response = await fetch(
        `/api/treatments/${encodeURIComponent(treatment.id)}`,
        {
          method: "PATCH",
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
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setEditMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de modifier le soin.",
        );
        return;
      }

      setIsEditOpen(false);
      router.refresh();
    } catch {
      setEditMessage(
        "Le serveur est momentanément indisponible.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    setIsDeleting(true);
    setDeleteMessage(null);

    try {
      const response = await fetch(
        `/api/treatments/${encodeURIComponent(treatment.id)}`,
        {
          method: "DELETE",
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setDeleteMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de supprimer le soin.",
        );
        return;
      }

      setIsDeleteOpen(false);
      router.refresh();
    } catch {
      setDeleteMessage(
        "Le serveur est momentanément indisponible.",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <>
      <div className="treatment-card-actions">
        <button
          className="patient-card-action edit"
          type="button"
          onClick={() => setIsEditOpen(true)}
        >
          <Pencil size={16} />
          Modifier
        </button>

        <button
          className="patient-card-action delete"
          type="button"
          onClick={() => setIsDeleteOpen(true)}
        >
          <Trash2 size={16} />
          Supprimer
        </button>
      </div>

      {isEditOpen ? (
        <div
          className="patient-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeEditModal();
            }
          }}
        >
          <section
            className="patient-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`treatment-edit-${treatment.id}`}
          >
            <header className="patient-modal-header">
              <div>
                <p className="eyebrow">Soins</p>
                <h2 id={`treatment-edit-${treatment.id}`}>
                  Modifier le soin
                </h2>
                <p>
                  Modifiez le prix, la durée ou les informations.
                </p>
              </div>

              <button
                className="patient-modal-close"
                type="button"
                onClick={closeEditModal}
                disabled={isSaving}
                aria-label="Fermer"
              >
                <X size={20} />
              </button>
            </header>

            <form
              className="patient-create-form"
              onSubmit={handleUpdate}
            >
              <label>
                Nom du soin
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  minLength={2}
                  maxLength={120}
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

              <div className="treatment-edit-sessions">
                <TreatmentSessionsManager
                  treatmentId={treatment.id}
                />
              </div>

              {editMessage ? (
                <p className="patient-form-error">
                  {editMessage}
                </p>
              ) : null}

              <div className="patient-modal-actions">
                <button
                  className="patient-secondary-button"
                  type="button"
                  onClick={closeEditModal}
                  disabled={isSaving}
                >
                  Annuler
                </button>

                <button
                  className="patient-primary-button"
                  type="submit"
                  disabled={isSaving}
                >
                  {isSaving ? "Enregistrement…" : "Enregistrer"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {isDeleteOpen ? (
        <div
          className="patient-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeDeleteModal();
            }
          }}
        >
          <section
            className="patient-modal patient-delete-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={`treatment-delete-${treatment.id}`}
          >
            <header className="patient-modal-header">
              <div className="patient-delete-heading">
                <span className="patient-delete-icon">
                  <AlertTriangle size={24} />
                </span>

                <div>
                  <p className="patient-delete-eyebrow">
                    Suppression définitive
                  </p>

                  <h2 id={`treatment-delete-${treatment.id}`}>
                    Supprimer {treatment.name} ?
                  </h2>
                </div>
              </div>

              <button
                className="patient-modal-close"
                type="button"
                onClick={closeDeleteModal}
                disabled={isDeleting}
                aria-label="Fermer"
              >
                <X size={20} />
              </button>
            </header>

            <div className="patient-delete-content">
              <p>
                Le soin sera retiré du catalogue. Les anciens
                rendez-vous resteront conservés.
              </p>

              <p className="patient-delete-warning">
                Cette opération est irréversible.
              </p>

              {deleteMessage ? (
                <p className="patient-form-error">
                  {deleteMessage}
                </p>
              ) : null}

              <div className="patient-modal-actions">
                <button
                  className="patient-secondary-button"
                  type="button"
                  onClick={closeDeleteModal}
                  disabled={isDeleting}
                >
                  Annuler
                </button>

                <button
                  className="patient-danger-button"
                  type="button"
                  onClick={handleDelete}
                  disabled={isDeleting}
                >
                  <Trash2 size={17} />
                  {isDeleting
                    ? "Suppression…"
                    : "Supprimer définitivement"}
                </button>
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
