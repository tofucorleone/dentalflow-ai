"use client";

import {
  Bot,
  CheckCheck,
  Clock3,
  Inbox,
  Info,
  MessageCircle,
  Phone,
  UserRound,
  Wifi,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ConversationCopilotPanel } from "@/components/conversation-copilot-panel";

export type ConversationChannel =
  | "whatsapp"
  | "phone"
  | "email"
  | "sms"
  | "web";

export type ConversationControlMode =
  | "ai_active"
  | "human_active"
  | "paused"
  | "closed";

export type ConversationLastMessage = {
  id: string;
  body: string | null;
  direction: "inbound" | "outbound";
  author_type: "patient" | "ai" | "human" | "system";
  occurred_at: string;
};

export type ConversationThread = {
  id: string;
  clinic_id: string;
  patient_id: string | null;
  patient_name: string | null;
  channel: ConversationChannel;
  sender_phone: string;
  provider: string | null;
  provider_instance: string | null;
  external_thread_id: string | null;
  assigned_user_id: string | null;
  status: "open" | "closed";
  unread_count: number;
  last_message_at: string | null;
  control_mode: ConversationControlMode;
  taken_over_by_user_id: string | null;
  taken_over_at: string | null;
  last_message: ConversationLastMessage | null;
  created_at: string;
  updated_at: string;
};

export type ConversationThreadListResponse = {
  items: ConversationThread[];
  total: number;
  limit: number;
  offset: number;
};

export type ConversationMessage = {
  id: string;
  clinic_id: string;
  thread_id: string;
  patient_id: string | null;
  sent_by_user_id: string | null;
  channel: ConversationChannel;
  direction: "inbound" | "outbound";
  author_type: "patient" | "ai" | "human" | "system";
  message_type:
    | "text"
    | "image"
    | "audio"
    | "video"
    | "document"
    | "location"
    | "system";
  body: string | null;
  external_id: string | null;
  provider: string | null;
  status:
    | "received"
    | "prepared"
    | "sent"
    | "delivered"
    | "read"
    | "failed";
  requires_validation: boolean;
  metadata: Record<string, unknown>;
  occurred_at: string;
  created_at: string;
  updated_at: string;
};

type ConversationMessageListResponse = {
  thread_id: string;
  items: ConversationMessage[];
  total: number;
  limit: number;
  offset: number;
};

type ConversationSendResponse = {
  message: ConversationMessage;
};

type ConversationInboxProps = {
  initialData: ConversationThreadListResponse;
};

function displayName(thread: ConversationThread): string {
  const name = thread.patient_name?.trim();

  if (name && !name.includes("{{")) {
    return name;
  }

  if (!thread.sender_phone.includes("{{")) {
    return thread.sender_phone;
  }

  return "Conversation de test";
}

function initials(thread: ConversationThread): string {
  const label = displayName(thread);
  const parts = label
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);

  return parts.map((part) => part.charAt(0).toUpperCase()).join("") || "?";
}

function safeMessage(value: string | null): string {
  if (!value || value.includes("{{$json.")) {
    return "Message non disponible";
  }

  return value;
}

function formatRelativeDate(value: string | null): string {
  if (!value) {
    return "Aucun message";
  }

  const date = new Date(value);
  const diffMinutes = Math.max(
    0,
    Math.round((Date.now() - date.getTime()) / 60000),
  );

  if (diffMinutes < 1) return "À l’instant";
  if (diffMinutes < 60) return `Il y a ${diffMinutes} min`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `Il y a ${diffHours} h`;

  return new Intl.DateTimeFormat("fr-DZ", {
    day: "2-digit",
    month: "short",
  }).format(date);
}

function formatMessageTime(value: string): string {
  return new Intl.DateTimeFormat("fr-DZ", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function modeLabel(mode: ConversationControlMode): string {
  if (mode === "human_active") return "Secrétaire active";
  if (mode === "paused") return "IA en pause";
  if (mode === "closed") return "Conversation fermée";
  return "IA active";
}

function authorLabel(message: ConversationMessage): string {
  if (message.author_type === "ai") return "DentalFlow AI";
  if (message.author_type === "human") return "Équipe clinique";
  if (message.author_type === "system") return "WhatsApp";
  return "Patient";
}

export function ConversationInbox({
  initialData,
}: ConversationInboxProps) {
  const [threads, setThreads] = useState<ConversationThread[]>(
    initialData.items,
  );
  const [threadTotal, setThreadTotal] = useState(initialData.total);
  const [selectedId, setSelectedId] = useState<string | null>(
    initialData.items[0]?.id ?? null,
  );
  const [selectedThread, setSelectedThread] =
    useState<ConversationThread | null>(threads[0] ?? null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(Boolean(threads[0]));
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [changingControl, setChangingControl] = useState(false);
  const [controlError, setControlError] = useState<string | null>(null);

  async function markConversationRead(threadId: string) {
    const thread = threads.find((item) => item.id === threadId);

    if (!thread || thread.unread_count <= 0) {
      return;
    }

    try {
      const response = await fetch(
        `/api/conversations/${threadId}/read`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        console.error(
          `Impossible de marquer la conversation comme lue (${response.status}).`,
        );
        return;
      }

      setThreads((current) =>
        current.map((item) =>
          item.id === threadId
            ? {
                ...item,
                unread_count: 0,
              }
            : item,
        ),
      );

      setSelectedThread((current) =>
        current?.id === threadId
          ? {
              ...current,
              unread_count: 0,
            }
          : current,
      );
    } catch (error) {
      console.error(
        "Impossible de marquer la conversation comme lue.",
        error,
      );
    }
  }

  async function changeConversationControl() {
    if (!selectedThread || changingControl) return;

    const mode: "ai_active" | "human_active" =
      selectedThread.control_mode === "ai_active"
        ? "human_active"
        : "ai_active";

    setChangingControl(true);
    setControlError(null);

    try {
      const response = await fetch(
        `/api/copilot/conversations/${selectedThread.id}/control`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ mode }),
        },
      );

      const body = (await response.json()) as {
        detail?: string;
        mode?: "ai_active" | "human_active";
        taken_over_by_user_id?: string | null;
        taken_over_at?: string | null;
      };

      if (!response.ok || !body.mode) {
        throw new Error(
          body.detail ??
            `Changement de contrôle impossible (${response.status}).`,
        );
      }

      setSelectedThread((current) =>
        current
          ? {
              ...current,
              control_mode: body.mode!,
              taken_over_by_user_id:
                body.taken_over_by_user_id ?? null,
              taken_over_at: body.taken_over_at ?? null,
            }
          : current,
      );

      setThreads((current) =>
        current.map((thread) =>
          thread.id === selectedThread.id
            ? {
                ...thread,
                control_mode: body.mode!,
                taken_over_by_user_id:
                  body.taken_over_by_user_id ?? null,
                taken_over_at: body.taken_over_at ?? null,
              }
            : thread,
        ),
      );
    } catch (caughtError) {
      setControlError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible de modifier le contrôle de la conversation.",
      );
    } finally {
      setChangingControl(false);
    }
  }

  const selectedFromList = useMemo(
    () => threads.find((thread) => thread.id === selectedId) ?? null,
    [selectedId, threads],
  );

  useEffect(() => {
    const requestedThreadId = new URLSearchParams(
      window.location.search,
    ).get("thread_id")?.trim();

    if (!requestedThreadId) {
      return;
    }

    const requestedThread = initialData.items.find(
      (thread) => thread.id === requestedThreadId,
    );

    if (!requestedThread) {
      return;
    }

    setSelectedId(requestedThread.id);
    setSelectedThread(requestedThread);
  }, [initialData.items]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedThread(null);
      setMessages([]);
      setLoading(false);
      return;
    }

    const controller = new AbortController();

    async function loadConversation() {
      setLoading(true);
      setError(null);

      try {
        const [threadResponse, messagesResponse] = await Promise.all([
          fetch(`/api/conversations/${selectedId}`, {
            cache: "no-store",
            signal: controller.signal,
          }),
          fetch(
            `/api/conversations/${selectedId}/messages?limit=200&offset=0`,
            {
              cache: "no-store",
              signal: controller.signal,
            },
          ),
        ]);

        if (!threadResponse.ok) {
          throw new Error(
            `Conversation indisponible (${threadResponse.status}).`,
          );
        }

        if (!messagesResponse.ok) {
          throw new Error(
            `Historique indisponible (${messagesResponse.status}).`,
          );
        }

        const thread = (await threadResponse.json()) as ConversationThread;
        const history =
          (await messagesResponse.json()) as ConversationMessageListResponse;

        let displayedThread = thread;

        if (thread.unread_count > 0) {
          const readResponse = await fetch(
            `/api/conversations/${selectedId}/read`,
            {
              method: "POST",
              signal: controller.signal,
            },
          );

          if (readResponse.ok) {
            displayedThread = {
              ...thread,
              unread_count: 0,
            };

            setThreads((current) =>
              current.map((item) =>
                item.id === selectedId
                  ? {
                      ...item,
                      unread_count: 0,
                    }
                  : item,
              ),
            );
          } else {
            console.error(
              `Impossible de marquer la conversation comme lue (${readResponse.status}).`,
            );
          }
        }

        setSelectedThread(displayedThread);
        setMessages(history.items);
      } catch (caughtError) {
        if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
          return;
        }

        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger la conversation.",
        );
        setSelectedThread(selectedFromList);
        setMessages([]);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadConversation();

    return () => controller.abort();
  }, [selectedId]);

  useEffect(() => {
    const container = messageScrollRef.current;

    if (!container || loading) {
      return;
    }

    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  }, [messages, loading, selectedId]);

  useEffect(() => {
    const eventSource = new EventSource(
      "/api/conversations/events",
    );

    const handleConversationMessage = (
      event: Event,
    ) => {
      const messageEvent =
        event as MessageEvent<string>;

      try {
        const payload = JSON.parse(
          messageEvent.data,
        ) as {
          thread_id?: string;
          message?: ConversationMessage;
        };

        if (
          !payload.thread_id ||
          !payload.message
        ) {
          return;
        }

        scheduleThreadListRefresh();

        if (payload.thread_id !== selectedId) {
          return;
        }

        const realtimeMessage = payload.message;

        setMessages((currentMessages) => {
          const existingIndex =
            currentMessages.findIndex(
              (message) =>
                message.id === realtimeMessage.id,
            );

          if (existingIndex === -1) {
            return [
              ...currentMessages,
              realtimeMessage,
            ];
          }

          return currentMessages.map(
            (message, index) =>
              index === existingIndex
                ? realtimeMessage
                : message,
          );
        });
      } catch {
        // Un événement SSE invalide est ignoré.
      }
    };

    let refreshTimer: ReturnType<
      typeof setTimeout
    > | null = null;
    let listRefreshTimer: ReturnType<
      typeof setTimeout
    > | null = null;

    const scheduleThreadListRefresh = () => {
      if (listRefreshTimer) {
        clearTimeout(listRefreshTimer);
      }

      listRefreshTimer = setTimeout(() => {
        async function refreshThreadList() {
          try {
            const response = await fetch(
              "/api/conversations?limit=50&offset=0&status=open",
              {
                cache: "no-store",
              },
            );

            if (!response.ok) {
              return;
            }

            const data =
              (await response.json()) as
                ConversationThreadListResponse;

            setThreads(data.items);
            setThreadTotal(data.total);
            setSelectedId((currentSelectedId) => {
              if (
                currentSelectedId &&
                data.items.some(
                  (thread) =>
                    thread.id === currentSelectedId,
                )
              ) {
                return currentSelectedId;
              }

              return data.items[0]?.id ?? null;
            });
          } catch {
            // Le prochain événement SSE réessaiera.
          }
        }

        void refreshThreadList();
      }, 150);
    };

    const handleConversationRefresh = (
      event: Event,
    ) => {
      const messageEvent =
        event as MessageEvent<string>;

      try {
        const payload = JSON.parse(
          messageEvent.data,
        ) as {
          thread_id?: string;
          message_id?: string;
        };

        if (!payload.thread_id) {
          return;
        }

        scheduleThreadListRefresh();

        if (payload.thread_id !== selectedId) {
          return;
        }
      } catch {
        return;
      }

      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }

      refreshTimer = setTimeout(() => {
        async function refreshConversation() {
          if (!selectedId) {
            return;
          }

          try {
            const [
              threadResponse,
              messagesResponse,
            ] = await Promise.all([
              fetch(
                `/api/conversations/${selectedId}`,
                {
                  cache: "no-store",
                },
              ),
              fetch(
                `/api/conversations/${selectedId}/messages?limit=200&offset=0`,
                {
                  cache: "no-store",
                },
              ),
            ]);

            if (
              !threadResponse.ok ||
              !messagesResponse.ok
            ) {
              return;
            }

            const thread =
              (await threadResponse.json()) as
                ConversationThread;

            const history =
              (await messagesResponse.json()) as
                ConversationMessageListResponse;

            setSelectedThread(thread);
            setMessages(history.items);
          } catch {
            // Le prochain événement ou rechargement
            // récupérera l’état courant.
          }
        }

        void refreshConversation();
      }, 200);
    };

    eventSource.addEventListener(
      "conversation.message.sent",
      handleConversationMessage,
    );

    eventSource.addEventListener(
      "conversation.message.failed",
      handleConversationMessage,
    );

    eventSource.addEventListener(
      "conversation.message.received",
      handleConversationRefresh,
    );

    eventSource.addEventListener(
      "conversation.message.prepared",
      handleConversationRefresh,
    );

    return () => {
      eventSource.removeEventListener(
        "conversation.message.sent",
        handleConversationMessage,
      );

      eventSource.removeEventListener(
        "conversation.message.failed",
        handleConversationMessage,
      );

      eventSource.removeEventListener(
        "conversation.message.received",
        handleConversationRefresh,
      );

      eventSource.removeEventListener(
        "conversation.message.prepared",
        handleConversationRefresh,
      );

      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }

      if (listRefreshTimer) {
        clearTimeout(listRefreshTimer);
      }

      eventSource.close();
    };
  }, [selectedId]);

  async function sendMessage() {
    if (!selectedThread || sending) {
      return;
    }

    const message = draft.trim();

    if (!message) {
      setSendError("Saisissez un message avant l’envoi.");
      return;
    }

    setSending(true);
    setSendError(null);

    try {
      const response = await fetch(
        `/api/conversations/${selectedThread.id}/send`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ message }),
        },
      );

      const responseBody = (await response.json()) as
        | ConversationSendResponse
        | { detail?: string };

      if (!response.ok) {
        const detail =
          "detail" in responseBody && responseBody.detail
            ? responseBody.detail
            : `Échec de l’envoi (${response.status}).`;

        throw new Error(detail);
      }

      if (!("message" in responseBody)) {
        throw new Error("Réponse d’envoi invalide.");
      }

      const sentMessage = responseBody.message;

      setMessages((currentMessages) => {
        const existingIndex =
          currentMessages.findIndex(
            (message) =>
              message.id === sentMessage.id,
          );

        if (existingIndex === -1) {
          return [
            ...currentMessages,
            sentMessage,
          ];
        }

        return currentMessages.map(
          (message, index) =>
            index === existingIndex
              ? sentMessage
              : message,
        );
      });

      if (sentMessage.status === "failed") {
        setSendError(
          "Le message a été enregistré, mais l’envoi WhatsApp a échoué.",
        );
        return;
      }

      setDraft("");
    } catch (caughtError) {
      setSendError(
        caughtError instanceof Error
          ? caughtError.message
          : "Impossible d’envoyer le message.",
      );
    } finally {
      setSending(false);
    }
  }

  if (threads.length === 0) {
    return (
      <section className="inbox-empty-page">
        <Inbox size={32} />
        <h2>Aucune conversation</h2>
        <p>
          Les prochains messages WhatsApp apparaîtront ici dès leur
          réception.
        </p>
      </section>
    );
  }

  return (
    <section
      className={`conversation-inbox ${showInfo ? "with-info" : "without-info"}`}
      aria-label="Inbox conversations"
    >
      <aside className="conversation-list-panel">
        <div className="conversation-panel-header">
          <div>
            <span>Inbox</span>
            <h2>Conversations</h2>
          </div>
          <strong>{threadTotal}</strong>
        </div>

        <div className="conversation-thread-list">
          {threads.map((thread) => {
            const active = thread.id === selectedId;

            return (
              <button
                className={`conversation-thread-row${active ? " active" : ""}`}
                key={thread.id}
                onClick={() => {
                  setSelectedId(thread.id);
                  setShowInfo(false);
                  void markConversationRead(thread.id);
                }}
                type="button"
              >
                <span className="conversation-avatar">{initials(thread)}</span>

                <span className="conversation-thread-copy">
                  <span className="conversation-thread-title">
                    <strong>{displayName(thread)}</strong>
                    <time>{formatRelativeDate(thread.last_message_at)}</time>
                  </span>

                  <span className="conversation-thread-preview">
                    {thread.channel === "whatsapp" ? (
                      <MessageCircle size={13} />
                    ) : (
                      <Phone size={13} />
                    )}
                    <span>{safeMessage(thread.last_message?.body ?? null)}</span>
                  </span>
                </span>

                {thread.unread_count > 0 && (
                  <span className="conversation-unread-count">
                    {thread.unread_count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </aside>

      <div className="conversation-history-panel">
        {selectedThread ? (
          <>
            <header className="conversation-history-header">
              <div>
                <span className="conversation-avatar large">
                  {initials(selectedThread)}
                </span>
                <div>
                  <h2>{displayName(selectedThread)}</h2>
                  <p>
                    <MessageCircle size={14} />
                    WhatsApp · {selectedThread.sender_phone.includes("{{")
                      ? "Donnée de test"
                      : selectedThread.sender_phone}
                  </p>
                </div>
              </div>

              <div className="conversation-header-actions">
                <span
                  className={`conversation-mode ${selectedThread.control_mode}`}
                >
                  {selectedThread.control_mode === "ai_active" ? (
                    <Bot size={15} />
                  ) : (
                    <UserRound size={15} />
                  )}
                  {modeLabel(selectedThread.control_mode)}
                </span>

                {selectedThread.control_mode !== "closed" && (
                  <button
                    className="conversation-control-button"
                    disabled={changingControl}
                    onClick={() => void changeConversationControl()}
                    type="button"
                  >
                    {changingControl
                      ? "Mise à jour…"
                      : selectedThread.control_mode === "ai_active"
                        ? "Prendre la main"
                        : "Réactiver l’IA"}
                  </button>
                )}

                <button
                  aria-expanded={showInfo}
                  aria-label={
                    showInfo
                      ? "Fermer les informations"
                      : "Afficher les informations"
                  }
                  className={`conversation-info-button${showInfo ? " active" : ""}`}
                  onClick={() => setShowInfo((current) => !current)}
                  title="Informations et Copilote"
                  type="button"
                >
                  <Info size={18} />
                  <span>Infos</span>
                </button>

                {controlError && (
                  <span
                    className="conversation-header-control-error"
                    role="alert"
                  >
                    {controlError}
                  </span>
                )}
              </div>
            </header>

            <div
              className="conversation-message-scroll"
              ref={messageScrollRef}
            >
              {loading ? (
                <div className="conversation-loading-state">
                  <Clock3 size={22} />
                  Chargement de l’historique…
                </div>
              ) : error ? (
                <div className="conversation-error-state">{error}</div>
              ) : messages.length === 0 ? (
                <div className="conversation-loading-state">
                  Aucun message enregistré dans ce thread.
                </div>
              ) : (
                <div className="conversation-message-list">
                  {messages.map((message) => {
                    const outbound = message.direction === "outbound";

                    return (
                      <article
                        className={`conversation-message ${outbound ? "outbound" : "inbound"}`}
                        key={message.id}
                      >
                        <div className="conversation-message-meta">
                          <strong>{authorLabel(message)}</strong>
                          <time>{formatMessageTime(message.occurred_at)}</time>
                        </div>
                        <p>{safeMessage(message.body)}</p>
                        {outbound && (
                          <span className="conversation-message-status">
                            <CheckCheck size={13} />
                            {message.status}
                          </span>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </div>

            <footer className="conversation-readonly-composer">
              <div
                style={{
                  display: "flex",
                  flex: 1,
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <textarea
                  aria-label="Message WhatsApp"
                  disabled={sending}
                  maxLength={4000}
                  onChange={(event) => {
                    setDraft(event.target.value);
                    setSendError(null);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void sendMessage();
                    }
                  }}
                  placeholder="Écrivez votre message WhatsApp…"
                  rows={3}
                  style={{
                    width: "100%",
                    minHeight: 72,
                    resize: "vertical",
                    border: "1px solid rgba(15, 23, 42, 0.14)",
                    borderRadius: 12,
                    padding: "11px 13px",
                    font: "inherit",
                    background: "#ffffff",
                    color: "#0f172a",
                    outline: "none",
                  }}
                  value={draft}
                />

                {sendError && (
                  <span
                    role="alert"
                    style={{
                      color: "#b42318",
                      fontSize: 12,
                      fontWeight: 700,
                    }}
                  >
                    {sendError}
                  </span>
                )}
              </div>

              <button
                disabled={
                  sending ||
                  !draft.trim() ||
                  selectedThread.status !== "open" ||
                  selectedThread.channel !== "whatsapp" ||
                  !selectedThread.provider_instance
                }
                onClick={() => void sendMessage()}
                type="button"
              >
                {sending ? "Envoi…" : "Envoyer"}
              </button>
            </footer>
          </>
        ) : (
          <div className="conversation-loading-state">
            Sélectionnez une conversation.
          </div>
        )}
      </div>

      {showInfo && (
        <aside className="conversation-patient-panel">
        {selectedThread ? (
          <>
            <div className="conversation-patient-hero">
              <span className="conversation-avatar patient">
                {initials(selectedThread)}
              </span>
              <h2>{displayName(selectedThread)}</h2>
              <p>{selectedThread.patient_id ? "Patient identifié" : "Contact non rattaché"}</p>
            </div>

            <dl className="conversation-patient-details">
              <div>
                <dt>Téléphone</dt>
                <dd>
                  {selectedThread.sender_phone.includes("{{")
                    ? "Donnée de test à nettoyer"
                    : selectedThread.sender_phone}
                </dd>
              </div>
              <div>
                <dt>Canal</dt>
                <dd>WhatsApp</dd>
              </div>
              <div>
                <dt>Fournisseur</dt>
                <dd>{selectedThread.provider ?? "Non renseigné"}</dd>
              </div>
              <div>
                <dt>Instance</dt>
                <dd>
                  {selectedThread.provider_instance?.includes("{{")
                    ? "Donnée de test"
                    : selectedThread.provider_instance ?? "Non renseignée"}
                </dd>
              </div>
              <div>
                <dt>Messages non lus</dt>
                <dd>{selectedThread.unread_count}</dd>
              </div>
            </dl>

            <ConversationCopilotPanel
              onControlModeChanged={(mode, takenOverByUserId, takenOverAt) => {
                setSelectedThread((current) =>
                  current
                    ? {
                        ...current,
                        control_mode: mode,
                        taken_over_by_user_id: takenOverByUserId,
                        taken_over_at: takenOverAt,
                      }
                    : current,
                );

                setThreads((current) =>
                  current.map((thread) =>
                    thread.id === selectedThread.id
                      ? {
                          ...thread,
                          control_mode: mode,
                          taken_over_by_user_id: takenOverByUserId,
                          taken_over_at: takenOverAt,
                        }
                      : thread,
                  ),
                );
              }}
              onPrepareAppointment={(patientId) => {
                const parameters = new URLSearchParams({
                  patient_id: patientId,
                  source: "copilot",
                  thread_id: selectedThread.id,
                });
                window.location.href = `/appointments?${parameters.toString()}`;
              }}
              onPrepareReschedule={(patientId, appointmentId) => {
                const parameters = new URLSearchParams({
                  mode: "reschedule",
                  appointment_id: appointmentId,
                  patient_id: patientId,
                  source: "copilot",
                  thread_id: selectedThread.id,
                });
                window.location.href = `/appointments?${parameters.toString()}`;
              }}
              onUseDraft={(message) => {
                setDraft(message);
                setSendError(null);
              }}
              refreshToken={
                messages.at(-1)?.updated_at ??
                selectedThread.updated_at
              }
              threadId={selectedThread.id}
            />
          </>
        ) : null}
        </aside>
      )}
    </section>
  );
}
