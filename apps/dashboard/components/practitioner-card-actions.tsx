"use client";

import {
  AlertTriangle,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

type PractitionerTreatment = {
  id: string;
  name: string;
  description: string | null;
  duration_minutes: number;
  price: number;
  active: boolean;
  selected: boolean;
};

type PractitionerCardActionsProps = {
  practitioner: {
    id: string;
    full_name: string;
    speciality: string | null;
    google_calendar_id: string | null;
    phone: string | null;
    email: string | null;
    active: boolean;
  };
};

export function PractitionerCardActions({
  practitioner,
}: PractitionerCardActionsProps) {
  const router = useRouter();

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const [treatments, setTreatments] = useState<
    PractitionerTreatment[]
  >([]);
  const [selectedTreatmentIds, setSelectedTreatmentIds] =
    useState<string[]>([]);
  const [isLoadingTreatments, setIsLoadingTreatments] =
    useState(false);

  const [fullName, setFullName] = useState(
    practitioner.full_name,
  );
  const [speciality, setSpeciality] = useState(
    practitioner.speciality ?? "",
  );
  const [googleCalendarId, setGoogleCalendarId] = useState(
    practitioner.google_calendar_id ?? "",
  );
  const [phone, setPhone] = useState(
    practitioner.phone ?? "",
  );
  const [email, setEmail] = useState(
    practitioner.email ?? "",
  );
  const [active, setActive] = useState(
    practitioner.active,
  );

  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [editMessage, setEditMessage] =
    useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] =
    useState<string | null>(null);

  async function openEditModal() {
    setIsEditOpen(true);
    setEditMessage(null);
    setIsLoadingTreatments(true);

    try {
      const response = await fetch(
        `/api/practitioners/${encodeURIComponent(
          practitioner.id,
        )}/treatments`,
      );

      const body = await response.json();

      if (!response.ok) {
        setEditMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de charger les soins.",
        );
        return;
      }

      const items = body as PractitionerTreatment[];

      setTreatments(items);
      setSelectedTreatmentIds(
        items
          .filter((item) => item.selected)
          .map((item) => item.id),
      );
    } catch {
      setEditMessage(
        "Impossible de charger les soins du praticien.",
      );
    } finally {
      setIsLoadingTreatments(false);
    }
  }

  function toggleTreatment(treatmentId: string) {
    setSelectedTreatmentIds((current) =>
      current.includes(treatmentId)
        ? current.filter((id) => id !== treatmentId)
        : [...current, treatmentId],
    );
  }

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

  async function handleUpdate(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setIsSaving(true);
    setEditMessage(null);

    try {
      const response = await fetch(
        `/api/practitioners/${encodeURIComponent(
          practitioner.id,
        )}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            full_name: fullName.trim(),
            speciality: speciality.trim() || null,
            google_calendar_id:
              googleCalendarId.trim() || null,
            phone: phone.trim() || null,
            email: email.trim() || null,
            active,
          }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setEditMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de modifier le praticien.",
        );
        return;
      }

      const treatmentsResponse = await fetch(
        `/api/practitioners/${encodeURIComponent(
          practitioner.id,
        )}/treatments`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(selectedTreatmentIds),
        },
      );

      const treatmentsBody = await treatmentsResponse.json();

      if (!treatmentsResponse.ok) {
        setEditMessage(
          typeof treatmentsBody.detail === "string"
            ? treatmentsBody.detail
            : "Impossible d’enregistrer les soins réalisés.",
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
        `/api/practitioners/${encodeURIComponent(
          practitioner.id,
        )}`,
        {
          method: "DELETE",
        },
      );

      const body = await response.json();

      if (!response.ok) {
        setDeleteMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de supprimer le praticien.",
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
      <div className="practitioner-card-actions">
        <button
          className="patient-card-action edit"
          type="button"
          onClick={openEditModal}
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
            aria-labelledby={`practitioner-edit-${practitioner.id}`}
          >
            <header className="patient-modal-header">
              <div>
                <p className="eyebrow">Praticiens</p>

                <h2
                  id={`practitioner-edit-${practitioner.id}`}
                >
                  Modifier le praticien
                </h2>

                <p>
                  Modifiez son identité, sa spécialité et son
                  calendrier.
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
                Nom complet
                <input
                  value={fullName}
                  onChange={(event) =>
                    setFullName(event.target.value)
                  }
                  minLength={2}
                  maxLength={150}
                  required
                />
              </label>

              <label>
                Spécialité
                <input
                  value={speciality}
                  onChange={(event) =>
                    setSpeciality(event.target.value)
                  }
                  maxLength={150}
                  placeholder="Ex. Orthodontiste"
                />
              </label>

              <label>
                Téléphone
                <input
                  value={phone}
                  onChange={(event) =>
                    setPhone(event.target.value)
                  }
                  maxLength={40}
                  placeholder="+213..."
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
                Google Calendar ID
                <input
                  value={googleCalendarId}
                  onChange={(event) =>
                    setGoogleCalendarId(event.target.value)
                  }
                  maxLength={500}
                  placeholder="calendar@group.calendar.google.com"
                />
              </label>

              <fieldset className="practitioner-treatments-fieldset">
                <legend>Soins réalisés</legend>

                <p>
                  Sélectionnez les prestations que ce praticien
                  peut effectuer.
                </p>

                {isLoadingTreatments ? (
                  <div className="practitioner-treatments-loading">
                    Chargement des soins…
                  </div>
                ) : treatments.length > 0 ? (
                  <div className="practitioner-treatments-grid">
                    {treatments.map((treatment) => (
                      <label
                        className="practitioner-treatment-option"
                        key={treatment.id}
                      >
                        <input
                          type="checkbox"
                          checked={selectedTreatmentIds.includes(
                            treatment.id,
                          )}
                          onChange={() =>
                            toggleTreatment(treatment.id)
                          }
                          disabled={!treatment.active}
                        />

                        <span>
                          <strong>{treatment.name}</strong>
                          <small>
                            {treatment.duration_minutes} minutes
                            {!treatment.active
                              ? " · Soin inactif"
                              : ""}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <div className="practitioner-treatments-loading">
                    Aucun soin configuré.
                  </div>
                )}
              </fieldset>

              <label className="treatment-checkbox-row">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={(event) =>
                    setActive(event.target.checked)
                  }
                />
                Praticien actif
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
            aria-labelledby={`practitioner-delete-${practitioner.id}`}
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

                  <h2
                    id={`practitioner-delete-${practitioner.id}`}
                  >
                    Supprimer {practitioner.full_name} ?
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
                Le praticien sera retiré de l’équipe. Les anciens
                rendez-vous resteront conservés dans DentalFlow.
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
