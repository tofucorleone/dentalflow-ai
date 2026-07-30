from __future__ import annotations

from typing import Any


MAX_HISTORY = 20


def format_history_for_llm(
    context: dict[str, Any] | None,
) -> str | None:
    """
    Convertit context["history"] en texte conversationnel
    destiné au Conversation Interpreter.
    """

    if not context:
        return None

    history = context.get("history")

    if not isinstance(history, list):
        return None

    lines: list[str] = []

    for message in history[-MAX_HISTORY:]:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")

        if not isinstance(role, str):
            continue

        if not isinstance(content, str):
            continue

        role = role.lower()

        if role == "user":
            prefix = "Patient"

        elif role == "assistant":
            prefix = "Assistant"

        else:
            prefix = role.capitalize()

        lines.append(
            f"{prefix}: {content.strip()}"
        )

    if not lines:
        return None

    return "\n".join(lines)
