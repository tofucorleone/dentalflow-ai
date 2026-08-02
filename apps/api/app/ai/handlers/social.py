from app.ai.schemas import ConversationResult


def handle_thanks(
    patient: dict | None,
) -> ConversationResult:
    return ConversationResult(
        intent="thanks",
        patient_id=patient["id"] if patient else None,
        reply=(
            "Avec plaisir 😊 "
            "N’hésitez pas si vous avez une autre question."
        ),
    )


def handle_goodbye(
    patient: dict | None,
) -> ConversationResult:
    return ConversationResult(
        intent="goodbye",
        patient_id=patient["id"] if patient else None,
        reply=(
            "Au revoir 👋 "
            "Je vous souhaite une excellente journée."
        ),
    )


__all__ = [
    "handle_goodbye",
    "handle_thanks",
]
