"use client";

import {
  ArrowRight,
  Bot,
  LoaderCircle,
  Send,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

type CopilotAction = {
  type: "navigate";
  label: string;
  href: string;
};

type CopilotChatResponse = {
  answer: string;
  intent:
    | "open_patient"
    | "patient_search"
    | "next_practitioner_appointment"
    | "practitioner_search"
    | "patient_next_appointment"
    | "planner_summary"
    | "recall"
    | "schedule"
    | "navigation"
    | "unsupported";
  actions: CopilotAction[];
  sources: {
    type:
      | "patient"
      | "practitioner"
      | "appointment";
    id: string;
    label: string;
  }[];
  suggestions: string[];
  requires_validation: boolean;
};

type ChatMessage =
  | {
      id: string;
      role: "user";
      content: string;
    }
  | {
      id: string;
      role: "assistant";
      content: string;
      actions: CopilotAction[];
      suggestions: string[];
    };

const suggestions = [
  "Ouvre la fiche de Ahmed Benali",
  "Qui vient aujourd’hui ?",
  "Quel est le prochain rendez-vous du Dr Sara ?",
];

export function CopilotChatPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Bonjour. Je peux rechercher un patient, consulter le planning, retrouver le prochain rendez-vous d’un praticien et ouvrir les pages de DentalFlow.",
      actions: [],
      suggestions: [
        "Qui vient aujourd’hui ?",
        "Ouvre les patients",
        "Ouvre les paramètres",
      ],
    },
  ]);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(
    message: string,
  ): Promise<void> {
    const cleanedMessage = message.trim();

    if (!cleanedMessage || sending) {
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: cleanedMessage,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);
    setInput("");
    setError(null);
    setSending(true);

    try {
      const response = await fetch(
        "/api/copilot/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: cleanedMessage,
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

      const result =
        body as CopilotChatResponse;

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.answer,
          actions: result.actions,
          suggestions: result.suggestions ?? [],
        },
      ]);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de contacter le Copilote.",
      );
    } finally {
      setSending(false);
    }
  }

  function submit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    void sendMessage(input);
  }

  return (
    <>
      {!isOpen && (
        <button
          type="button"
          className="copilot-chat-launcher"
          onClick={() => setIsOpen(true)}
          aria-label="Ouvrir le Copilote"
          title="Demander au Copilote"
        >
          <Bot size={24} />
          <span>Copilote</span>
        </button>
      )}

      {isOpen && (
        <section className="copilot-chat-panel copilot-chat-floating">
          <button
            type="button"
            className="copilot-chat-close"
            onClick={() => setIsOpen(false)}
            aria-label="Fermer le Copilote"
            title="Fermer"
          >
            <X size={19} />
          </button>

          <div className="copilot-chat-heading">
        <div className="copilot-chat-heading-icon">
          <Bot size={22} />
        </div>

        <div>
          <span>Assistant conversationnel</span>
          <h2>Demander au Copilote</h2>
          <p>
            Recherchez un patient et accédez
            directement à sa fiche.
          </p>
        </div>
      </div>

      <div className="copilot-chat-messages">
        {messages.map((message) => (
          <article
            className={`copilot-chat-message ${message.role}`}
            key={message.id}
          >
            <div className="copilot-chat-avatar">
              {message.role === "assistant" ? (
                <Bot size={17} />
              ) : (
                <UserRound size={17} />
              )}
            </div>

            <div className="copilot-chat-bubble">
              <p>{message.content}</p>

              {message.role === "assistant" &&
                message.actions.length > 0 && (
                  <div className="copilot-chat-actions">
                    {message.actions.map((action) => (
                      <Link
                        className="copilot-chat-link"
                        href={action.href}
                        key={`${action.href}-${action.label}`}
                      >
                        {action.label}
                        <ArrowRight size={15} />
                      </Link>
                    ))}
                  </div>
                )}

              {message.role === "assistant" &&
                message.suggestions.length > 0 && (
                  <div className="copilot-chat-message-suggestions">
                    {message.suggestions.map(
                      (suggestion) => (
                        <button
                          type="button"
                          key={suggestion}
                          disabled={sending}
                          onClick={() => {
                            void sendMessage(suggestion);
                          }}
                        >
                          {suggestion}
                        </button>
                      ),
                    )}
                  </div>
                )}
            </div>
          </article>
        ))}

        {sending && (
          <article className="copilot-chat-message assistant">
            <div className="copilot-chat-avatar">
              <Bot size={17} />
            </div>

            <div className="copilot-chat-thinking">
              <LoaderCircle
                className="copilot-spinner"
                size={17}
              />
              Le Copilote recherche…
            </div>
          </article>
        )}
      </div>

      {error && (
        <p
          className="copilot-chat-error"
          role="alert"
        >
          {error}
        </p>
      )}

      <div className="copilot-chat-suggestions">
        {suggestions.map((suggestion) => (
          <button
            type="button"
            key={suggestion}
            onClick={() => {
              void sendMessage(suggestion);
            }}
            disabled={sending}
          >
            {suggestion}
          </button>
        ))}
      </div>

      <form
        className="copilot-chat-form"
        onSubmit={submit}
      >
        <label htmlFor="copilot-chat-input">
          Question au Copilote
        </label>

        <div className="copilot-chat-input-row">
          <input
            id="copilot-chat-input"
            type="text"
            value={input}
            onChange={(event) => {
              setInput(event.target.value);
            }}
            placeholder="Ex. Ouvre la fiche de Ahmed Benali"
            autoComplete="off"
            disabled={sending}
          />

          <button
            type="submit"
            disabled={sending || !input.trim()}
            aria-label="Envoyer la question"
          >
            {sending ? (
              <LoaderCircle
                className="copilot-spinner"
                size={18}
              />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </form>
        </section>
      )}
    </>
  );
}
