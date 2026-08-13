from typing import Any


def build_copilot_response(
    *,
    answer: str,
    intent: str,
    actions: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    suggestions: list[str] | None = None,
    requires_validation: bool = False,
) -> dict[str, Any]:
    return {
        "answer": answer,
        "intent": intent,
        "actions": actions or [],
        "sources": sources or [],
        "suggestions": suggestions or [],
        "requires_validation": requires_validation,
    }
