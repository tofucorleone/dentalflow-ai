"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function PatientCreateForm() {
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [administrativeNotes, setAdministrativeNotes] =
    useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function closeForm() {
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
      const response = await fetch("/api/patients", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          phone: phone.trim(),
          full_name: fullName.trim() || null,
          email: email.trim() || null,
          administrative_notes:
            administrativeNotes.trim() || null,
        }),
      });

      const body = await response.json();

      if (!response.ok) {
        setMessage(
          typeof body.detail === "string"
            ? body.detail
            : "Impossible de créer le patient.",
        );
        return;
      }

      setFullName("");
      setPhone("");
      setEmail("");
      setAdministrativeNotes("");
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
        className="patient-create-trigger"
        type="button"
        onClick={() => setIsOpen(true)}
      >
        <Plus size={19} />
        Nouveau patient
      </button>

      {isOpen ? (
        <div
          className="patient-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeForm();
            }
          }}
        >
          <section
            className="patient-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="patient-create-title"
          >
            <header className="patient-modal-header">
              <div>
                <p className="eyebrow">Patients</p>
                <h2 id="patient-create-title">
                  Nouveau patient
                </h2>
                <p>
                  Ajoutez les informations administratives du
                  patient.
                </p>
              </div>

              <button
                className="patient-modal-close"
                type="button"
                onClick={closeForm}
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
                  placeholder="Ex. Ahmed Benali"
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
                  placeholder="+213..."
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
                  placeholder="patient@example.com"
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
                  placeholder="Informations utiles pour l'équipe…"
                  maxLength={2000}
                />
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
                  onClick={closeForm}
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
                    : "Créer le patient"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}
