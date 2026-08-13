"use client";

import {
  Check,
  ClipboardCopy,
  LockKeyhole,
  MessageSquareText,
} from "lucide-react";
import { useState } from "react";

type Props = {
  draftMessage: string;
};

export function CopilotOverdueDraftActions({
  draftMessage,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setError("Impossible de copier le brouillon.");
    }
  }

  return (
    <div className="copilot-overdue-draft">
      <button
        className="copilot-overdue-draft-toggle"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
      >
        <MessageSquareText size={16} />
        {isOpen
          ? "Masquer le brouillon"
          : "Brouillon WhatsApp"}
      </button>

      {isOpen ? (
        <div className="copilot-overdue-draft-content">
          <pre>{draftMessage}</pre>

          <div className="copilot-overdue-draft-footer">
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

            <span className="copilot-draft-lock">
              <LockKeyhole size={14} />
              Aucun envoi automatique
            </span>
          </div>

          {error ? (
            <p className="copilot-copy-error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
