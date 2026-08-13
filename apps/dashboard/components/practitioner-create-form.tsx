"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function PractitionerCreateForm() {
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [speciality, setSpeciality] = useState("");
  const [googleCalendarId, setGoogleCalendarId] =
    useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [active, setActive] = useState(true);

  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] =
    useState<string | null>(null);

  function closeModal() {
    if (isSaving) {
      return;
    }

    setIsOpen(false);
    setMessage(null);
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setIsSaving(true);
    setMessage(null);

    try {
      const response = await fetch("/api/practitioners", {
        method: "POST",
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
      });

      const body = await response.json();

      if (!response.ok) {
        setMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de créer le praticien.",
        );
        return;
      }

      setFullName("");
      setSpeciality("");
      setGoogleCalendarId("");
      setPhone("");
      setEmail("");
      setActive(true);
      setIsOpen(false);

      router.refresh();
    } catch {
      setMessage(
        "Le serveur est momentanément indisponible.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <>
      <button
        className="practitioner-create-trigger"
        type="button"
        onClick={() => setIsOpen(true)}
      >
        <Plus size={19} />
        Nouveau praticien
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
            aria-labelledby="practitioner-create-title"
          >
            <header className="patient-modal-header">
              <div>
                <p className="eyebrow">Praticiens</p>
                <h2 id="practitioner-create-title">
                  Nouveau praticien
                </h2>
                <p>
                  Ajoutez un membre à l’équipe médicale.
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
                Nom complet
                <input
                  value={fullName}
                  onChange={(event) =>
                    setFullName(event.target.value)
                  }
                  minLength={2}
                  maxLength={150}
                  placeholder="Ex. Dr Ahmed Benali"
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
                  placeholder="docteur@clinique.com"
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

              {message ? (
                <p className="patient-form-error">
                  {message}
                </p>
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
                  {isSaving
                    ? "Création…"
                    : "Créer le praticien"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}
