"use client";

import {
  AlertTriangle,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

type PatientListActionsProps = {
  patient: {
    id: string;
    full_name: string | null;
    phone: string;
    email: string | null;
    administrative_notes: string | null;
  };
};

export function PatientListActions({
  patient,
}: PatientListActionsProps) {
  const router = useRouter();

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const [fullName, setFullName] = useState(
    patient.full_name ?? "",
  );
  const [phone, setPhone] = useState(patient.phone);
  const [email, setEmail] = useState(patient.email ?? "");
  const [administrativeNotes, setAdministrativeNotes] =
    useState(patient.administrative_notes ?? "");

  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editMessage, setEditMessage] =
    useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] =
    useState<string | null>(null);

  const patientName =
    patient.full_name?.trim() || "ce patient";

  function closeEditModal() {
    if (isSaving) {
      return;
    }

    setIsEditOpen(false);
    setEditMessage(null);
  }

  function closeDeleteModal() {
    if (isDeleting) {
      return;
    }

    setIsDeleteOpen(false);
    setDeleteMessage(null);
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setIsSaving(true);
    setEditMessage(null);

    try {
      const response = await fetch(
        `/api/patients/${encodeURIComponent(patient.id)}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            full_name: fullName.trim() || null,
            phone: phone.trim(),
            email: email.trim() || null,
            administrative_notes:
              administrativeNotes.trim() || null,
          }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setEditMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de modifier le patient.",
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
        `/api/patients/${encodeURIComponent(patient.id)}`,
        {
          method: "DELETE",
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setDeleteMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de supprimer le patient.",
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
      <div className="patient-card-action-group">
        <button
          className="patient-card-action edit"
          type="button"
          onClick={() => setIsEditOpen(true)}
          title="Modifier le patient"
        >
          <Pencil size={16} />
          Modifier
        </button>

        <button
          className="patient-card-action delete"
          type="button"
          onClick={() => setIsDeleteOpen(true)}
          title="Supprimer le patient"
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
            aria-labelledby={`patient-edit-${patient.id}`}
          >
            <header className="patient-modal-header">
              <div>
                <p className="eyebrow">Patients</p>

                <h2 id={`patient-edit-${patient.id}`}>
                  Modifier le patient
                </h2>

                <p>
                  Modifiez les informations administratives.
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
              onSubmit={handleSubmit}
            >
              <label>
                Nom complet
                <input
                  value={fullName}
                  onChange={(event) =>
                    setFullName(event.target.value)
                  }
                  maxLength={150}
                />
              </label>

              <label>
                Téléphone
                <input
                  value={phone}
                  onChange={(event) =>
                    setPhone(event.target.value)
                  }
                  minLength={6}
                  maxLength={40}
                  required
                />
              </label>

              <label>
                Adresse e-mail
                <input
                  type="email"
                  value={email}
                  onChange={(event) =>
                    setEmail(event.target.value)
                  }
                  maxLength={255}
                />
              </label>

              <label>
                Notes administratives
                <textarea
                  value={administrativeNotes}
                  onChange={(event) =>
                    setAdministrativeNotes(event.target.value)
                  }
                  maxLength={2000}
                />
              </label>

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
                  {isSaving
                    ? "Enregistrement…"
                    : "Enregistrer"}
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
            aria-labelledby={`patient-delete-${patient.id}`}
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

                  <h2 id={`patient-delete-${patient.id}`}>
                    Supprimer {patientName} ?
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
                Cette action supprimera définitivement le patient
                ainsi que ses données associées.
              </p>

              <ul>
                <li>Ses rendez-vous dans DentalFlow</li>
                <li>Les événements Google Calendar associés</li>
                <li>Les informations administratives du patient</li>
              </ul>

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
