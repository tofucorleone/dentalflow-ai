from app.ai.schemas import ConversationIntent


_INTENTS: dict[ConversationIntent, tuple[str, ...]] = {
    "greeting": (
        "bonjour",
        "bonsoir",
        "salut",
        "hello",
    ),
    "cancel_appointment": (
        "annuler",
        "annulation",
        "supprimer mon rendez-vous",
    ),
    "reschedule_appointment": (
        "déplacer",
        "déplace",
        "déplacez",
        "déplacement",
        "reporter",
        "reporte",
        "reportez",
        "changer mon rendez-vous",
        "change mon rendez-vous",
        "changez mon rendez-vous",
    ),
    "book_appointment": (
        "prendre rendez-vous",
        "prendre un rendez-vous",
        "rendez-vous",
        "rdv",
    ),
    "clinic_information": (
        "horaire",
        "horaires",
        "adresse",
        "telephone",
        "téléphone",
    ),
    "treatment_pricing": (
        "prix",
        "tarif",
        "tarifs",
        "combien coûte",
        "combien coute",
        "coût",
        "cout",
    ),
}


def detect_intent(message: str) -> ConversationIntent:
    text = message.strip().lower()

    for intent, keywords in _INTENTS.items():
        if any(keyword in text for keyword in keywords):
            return intent

    return "unknown"
