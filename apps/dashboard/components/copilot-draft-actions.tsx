"use client";

import {
  Check,
  ClipboardCopy,
  LoaderCircle,
  LockKeyhole,
  Save,
} from "lucide-react";
import { useState } from "react";

type Props = {
  patientId: string;
  appointmentId: string;
  practitionerId: string | null;
  treatmentId: string | null;
  startAt: string;
  endAt: string;
  draftMessage: string;
  candidateScore: number;
  matchLevel: "primary" | "secondary";
  reasons: string[];
  requiresValidation: boolean;
};

type RecallDraftResponse = {
  id: string;
  payload: {
    status: string;
    requires_validation: boolean;
  };
};

export function CopilotDraftActions({
  patientId,
  appointmentId,
  practitionerId,
  treatmentId,
  startAt,
  endAt,
  draftMessage,
  candidateScore,
  matchLevel,
  reasons,
  requiresValidation,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [preparedDraft, setPreparedDraft] =
    useState<RecallDraftResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [booking, setBooking] = useState(false);
  const [booked, setBooked] = useState(false);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  async function copyDraft() {
    setError(null);

    try {
      await navigator.clipboard.writeText(draftMessage);
      setCopied(true);

      window.setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch {
      setCopied(false);
      setError(
        "Impossible de copier automatiquement le brouillon.",
      );
    }
  }

  async function sendRecallProposal() {
    if (
      !preparedDraft ||
      sending ||
      sent ||
      booked
    ) {
      return;
    }

    const confirmed = window.confirm(
      "Valider et envoyer cette proposition WhatsApp au patient ?",
    );

    if (!confirmed) return;

    setError(null);
    setSending(true);

    try {
      const response = await fetch(
        "/api/copilot/recall/send",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            draft_id: preparedDraft.id,
            patient_id: patientId,
            appointment_id: appointmentId,
            practitioner_id: practitionerId,
            treatment_id: treatmentId,
            start_at: startAt,
            end_at: endAt,
            message: draftMessage,
          }),
        },
      );

      const text = await response.text();

      let body: unknown;

      try {
        body = JSON.parse(text);
      } catch {
        body = {
          detail:
            text || "Réponse invalide du serveur.",
        };
      }

      if (!response.ok) {
        const detail =
          typeof body === "object" &&
          body !== null &&
          "detail" in body
            ? String(body.detail)
            : `Erreur ${response.status}`;

        throw new Error(detail);
      }

      setSent(true);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d'envoyer la proposition WhatsApp.",
      );
    } finally {
      setSending(false);
    }
  }


  async function reserveReleasedSlot() {
    if (booked || booking) return;

    const confirmed = window.confirm(
      "Confirmer la réservation de ce créneau pour ce patient ?",
    );

    if (!confirmed) return;

    setError(null);
    setBooking(true);

    try {
      const response = await fetch("/api/appointments", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          patient_id: patientId,
          practitioner_id: practitionerId,
          treatment_id: treatmentId,
          channel: "dashboard",
          status: "confirmed",
          start_at: startAt,
          end_at: endAt,
          notes: "Créneau attribué depuis le Copilote DentalFlow AI.",
        }),
      });

      const text = await response.text();

      let body: unknown;

      try {
        body = JSON.parse(text);
      } catch {
        body = {
          detail: text || "Réponse invalide du serveur.",
        };
      }

      if (!response.ok) {
        const detail =
          typeof body === "object" &&
          body !== null &&
          "detail" in body
            ? String(body.detail)
            : `Erreur ${response.status}`;

        throw new Error(detail);
      }

      setBooked(true);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de réserver ce créneau.",
      );
    } finally {
      setBooking(false);
    }
  }


  async function prepareDraft() {
    setError(null);
    setPreparing(true);

    try {
      const response = await fetch(
        "/api/copilot/recall/drafts",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            patient_id: patientId,
            appointment_id: appointmentId,
            message: draftMessage,
            candidate_score: candidateScore,
            match_level: matchLevel,
            reasons,
          }),
        },
      );

      const text = await response.text();
      let body: unknown;

      try {
        body = JSON.parse(text);
      } catch {
        body = {
          detail:
            text || "Réponse invalide du serveur.",
        };
      }

      if (!response.ok) {
        const detail =
          typeof body === "object" &&
          body !== null &&
          "detail" in body
            ? String(body.detail)
            : `Erreur ${response.status}`;

        throw new Error(detail);
      }

      setPreparedDraft(body as RecallDraftResponse);
    } catch (caughtError) {
      setPreparedDraft(null);
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de préparer le brouillon.",
      );
    } finally {
      setPreparing(false);
    }
  }

  return (
    <div className="copilot-draft-actions">
      <button
        className="copilot-copy-button"
        type="button"
        onClick={copyDraft}
      >
        {copied ? (
          <>
            <Check size={16} />
            Brouillon copié
          </>
        ) : (
          <>
            <ClipboardCopy size={16} />
            Copier le brouillon
          </>
        )}
      </button>

      <button
        className="copilot-prepare-button"
        type="button"
        onClick={prepareDraft}
        disabled={preparing || preparedDraft !== null || booked}
      >
        {preparing ? (
          <>
            <LoaderCircle
              className="copilot-spinner"
              size={16}
            />
            Préparation…
          </>
        ) : preparedDraft ? (
          <>
            <Check size={16} />
            Brouillon préparé
          </>
        ) : (
          <>
            <Save size={16} />
            Préparer l’envoi
          </>
        )}
      </button>

      <button
        className="copilot-prepare-button"
        type="button"
        onClick={sendRecallProposal}
        disabled={
          !preparedDraft ||
          sending ||
          sent ||
          booked
        }
      >
        {sending ? (
          <>
            <LoaderCircle
              className="copilot-spinner"
              size={16}
            />
            Envoi WhatsApp…
          </>
        ) : sent ? (
          <>
            <Check size={16} />
            Proposition envoyée
          </>
        ) : (
          <>
            💬 Valider et envoyer WhatsApp
          </>
        )}
      </button>

      <button
        className="copilot-prepare-button"
        type="button"
        onClick={reserveReleasedSlot}
        disabled={booking || booked || sent}
      >
        {booking ? (
          <>
            <LoaderCircle
              className="copilot-spinner"
              size={16}
            />
            Réservation…
          </>
        ) : booked ? (
          <>
            <Check size={16} />
            Créneau réservé
          </>
        ) : (
          <>
            📅 Réserver ce créneau
          </>
        )}
      </button>

      {sent && (
        <div
          className="copilot-prepared-status"
          role="status"
        >
          <strong>
            En attente de la réponse du patient
          </strong>
          <span>
            OUI → création du rendez-vous
          </span>
          <small>
            NON → le créneau reste disponible.
          </small>
        </div>
      )}

      {requiresValidation && (
        <span className="copilot-draft-lock">
          <LockKeyhole size={14} />
          Aucun envoi sans validation
        </span>
      )}

      {preparedDraft && !sent && (
        <div
          className="copilot-prepared-status"
          role="status"
        >
          <strong>Statut : draft</strong>
          <span>
            Brouillon audité : {preparedDraft.id}
          </span>
          <small>
            Aucun message WhatsApp n’a été envoyé.
          </small>
        </div>
      )}

      {error && (
        <p className="copilot-copy-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
