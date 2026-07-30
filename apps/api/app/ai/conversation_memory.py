from __future__ import annotations

from typing import Any

MAX_HISTORY_MESSAGES = 20


def get_history(context: dict[str, Any] | None) -> list[dict[str, str]]:
    """
    Retourne l'historique conversationnel stocké dans context["history"].
    """

    if not context:
        return []

    history = context.get("history", [])

    if not isinstance(history, list):
        return []

    cleaned: list[dict[str, str]] = []

    for message in history:
        if (
            isinstance(message, dict)
            and isinstance(message.get("role"), str)
            and isinstance(message.get("content"), str)
        ):
            cleaned.append(
                {
                    "role": message["role"],
                    "content": message["content"],
                }
            )

    return cleaned


def append_message(
    context: dict[str, Any] | None,
    *,
    role: str,
    content: str,
) -> dict[str, Any]:
    """
    Ajoute un message à l'historique.
    Garde uniquement les N derniers messages.
    """

    updated = dict(context or {})

    history = get_history(updated)

    history.append(
        {
            "role": role,
            "content": content.strip(),
        }
    )

    updated["history"] = history[-MAX_HISTORY_MESSAGES:]

    return updated


def clear_history(
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Supprime uniquement l'historique.
    """

    updated = dict(context or {})
    updated.pop("history", None)
    return updated
