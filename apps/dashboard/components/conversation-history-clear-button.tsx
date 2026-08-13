"use client";

import { useState } from "react";

type ClearHistoryResponse = {
  cleared: boolean;
  deleted?: {
    conversation_history?: number;
    conversation_states?: number;
    conversation_threads?: number;
  };
};

export function ConversationHistoryClearButton() {
  const [clearing, setClearing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function clearHistory() {
    const confirmed = window.confirm(
      "Vider l’historique des conversations de cette clinique ?\n\n" +
        "Les conversations, messages et états conversationnels seront supprimés.\n" +
        "Les patients, rendez-vous et données métier seront conservés.",
    );

    if (!confirmed) {
      return;
    }

    setClearing(true);
    setMessage(null);
    setError(null);

    try {
      const response = await fetch(
        "/api/conversations/clear-history",
        {
          method: "POST",
        },
      );

      const body = (await response.json()) as
        | ClearHistoryResponse
        | { detail?: string };

      if (!response.ok) {
        const detail =
          "detail" in body && body.detail
            ? body.detail
            : `Échec de la suppression (${response.status}).`;

        throw new Error(detail);
      }

      if (!("cleared" in body) || !body.cleared) {
        throw new Error(
          "La suppression de l’historique n’a pas été confirmée.",
        );
      }

      const deleted = body.deleted;

      setMessage(
        deleted
          ? (
              `Historique vidé : ` +
              `${deleted.conversation_threads ?? 0} conversation(s) supprimée(s).`
            )
          : "Historique des conversations vidé.",
      );
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de vider l’historique des conversations.",
      );
    } finally {
      setClearing(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        className="patient-danger-button"
        onClick={clearHistory}
        disabled={clearing}
      >
        {clearing
          ? "Suppression en cours…"
          : "Vider l’historique des conversations"}
      </button>

      {message ? (
        <p role="status">{message}</p>
      ) : null}

      {error ? (
        <p role="alert">{error}</p>
      ) : null}
    </div>
  );
}
