from app.copilot.service import build_recall_message


def test_build_recall_message_with_practitioner():
    result = build_recall_message(
        patient_name="Farid",
        practitioner_name="Dr Martin",
        start_label="mardi 4 août à 15:00",
    )

    assert result == (
        "Bonjour Farid,\n\n"
        "Un créneau vient de se libérer avec Dr Martin "
        "le mardi 4 août à 15:00.\n\n"
        "Souhaitez-vous en profiter ?\n\n"
        "Répondez simplement OUI pour que nous puissions "
        "vous le réserver."
    )


def test_build_recall_message_without_practitioner():
    result = build_recall_message(
        patient_name="Farid",
        practitioner_name=None,
        start_label="mardi 4 août à 15:00",
    )

    assert result == (
        "Bonjour Farid,\n\n"
        "Un créneau vient de se libérer "
        "le mardi 4 août à 15:00.\n\n"
        "Souhaitez-vous en profiter ?\n\n"
        "Répondez simplement OUI pour que nous puissions "
        "vous le réserver."
    )
