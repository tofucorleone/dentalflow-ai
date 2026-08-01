"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

type ClinicBrandingFormProps = {
  initialDisplayName: string;
  initialSoftwareName: string;
};

export function ClinicBrandingForm({
  initialDisplayName,
  initialSoftwareName,
}: ClinicBrandingFormProps) {
  const router = useRouter();

  const [displayName, setDisplayName] = useState(
    initialDisplayName,
  );
  const [softwareName, setSoftwareName] = useState(
    initialSoftwareName,
  );
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  async function handleLogoUpload(
    event: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setUploadingLogo(true);
    setMessage(null);
    setIsError(false);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "/api/clinic-branding/logo",
        {
          method: "POST",
          body: formData,
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Impossible d’enregistrer le logo.",
        );
      }

      setMessage("Logo enregistré avec succès.");
      router.refresh();
    } catch (error) {
      setIsError(true);
      setMessage(
        error instanceof Error
          ? error.message
          : "Une erreur est survenue.",
      );
    } finally {
      setUploadingLogo(false);
      event.target.value = "";
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setSaving(true);
    setMessage(null);
    setIsError(false);

    try {
      const response = await fetch("/api/clinic-branding", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          display_name: displayName,
          software_name: softwareName,
        }),
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Impossible d’enregistrer les modifications.",
        );
      }

      setMessage("Identité enregistrée avec succès.");
      router.refresh();
    } catch (error) {
      setIsError(true);
      setMessage(
        error instanceof Error
          ? error.message
          : "Une erreur est survenue.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="settings-form" onSubmit={handleSubmit}>
      <label className="form-field">
        <span>Nom du logiciel</span>
        <input
          type="text"
          value={softwareName}
          onChange={(event) =>
            setSoftwareName(event.target.value)
          }
          minLength={1}
          maxLength={120}
          required
        />
      </label>

      <label className="form-field">
        <span>Nom affiché de la clinique</span>
        <input
          type="text"
          value={displayName}
          onChange={(event) =>
            setDisplayName(event.target.value)
          }
          minLength={1}
          maxLength={120}
          required
        />
      </label>

      <label className="form-field">
        <span>Logo de la clinique</span>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={handleLogoUpload}
          disabled={uploadingLogo}
        />
        <small>
          PNG, JPEG ou WebP — 5 Mo maximum.
        </small>
      </label>

      {message ? (
        <p
          className={
            isError
              ? "form-message error"
              : "form-message success"
          }
        >
          {message}
        </p>
      ) : null}

      <div className="form-actions">
        <button
          className="primary-button"
          type="submit"
          disabled={saving}
        >
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </form>
  );
}
