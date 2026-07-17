from app.ai.schemas import ConversationResult


def handle_greeting(
    patient: dict | None,
) -> ConversationResult:
    if patient:
        patient_name = patient["full_name"] or "cher patient"

        return ConversationResult(
            intent="greeting",
            patient_id=patient["id"],
            reply=(
                f"Bonjour {patient_name} 👋 "
                "Comment puis-je vous aider aujourd'hui ?"
            ),
        )

    return ConversationResult(
        intent="greeting",
        reply=(
            "Bonjour 👋 "
            "Je suis l'assistant de la clinique. "
            "Comment puis-je vous aider aujourd'hui ?"
        ),
    )
