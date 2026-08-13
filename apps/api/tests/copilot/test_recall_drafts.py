import asyncio
from uuid import uuid4

from app.copilot.service import create_recall_draft


class FakeCursor:
    def __init__(self):
        self.execute_count = 0
        self.query = None
        self.params = None
        self.row = None

    async def execute(self, query, params):
        self.execute_count += 1
        self.query = query
        self.params = params

        if self.execute_count == 1:
            self.row = None
            return

        if self.execute_count == 2:
            self.row = {
                "id": uuid4(),
                "clinic_id": params[0],
                "patient_id": params[1],
                "appointment_id": params[2],
                "channel": "whatsapp",
                "direction": "outbound",
                "event_type": "recall_draft",
                "external_id": None,
                "payload": params[3].obj,
            }
            return

        raise AssertionError(
            "execute() appelé à une étape inattendue : "
            f"{self.execute_count}"
        )

    async def fetchone(self):
        return self.row


def test_create_recall_draft_inserts_audited_event():
    clinic_id = uuid4()
    patient_id = uuid4()
    appointment_id = uuid4()
    user_id = uuid4()

    cursor = FakeCursor()

    result = asyncio.run(
        create_recall_draft(
            cur=cursor,
            clinic_id=clinic_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            message=(
                "Bonjour Patient Test,\n\n"
                "Un créneau vient de se libérer."
            ),
            candidate_score=55,
            match_level="secondary",
            reasons=[
                "Jour préféré correspondant",
                "Aucun rendez-vous actif futur",
            ],
            created_by_user_id=user_id,
        )
    )

    assert "INSERT INTO communication_events" in cursor.query
    assert "RETURNING" in cursor.query

    payload = cursor.params[3].obj

    assert payload == {
        "status": "draft",
        "message": (
            "Bonjour Patient Test,\n\n"
            "Un créneau vient de se libérer."
        ),
        "candidate_score": 55,
        "match_level": "secondary",
        "reasons": [
            "Jour préféré correspondant",
            "Aucun rendez-vous actif futur",
        ],
        "requires_validation": True,
        "created_by_user_id": str(user_id),
    }

    assert result["clinic_id"] == clinic_id
    assert result["patient_id"] == patient_id
    assert result["appointment_id"] == appointment_id
    assert result["channel"] == "whatsapp"
    assert result["direction"] == "outbound"
    assert result["event_type"] == "recall_draft"
    assert result["payload"]["status"] == "draft"


def test_create_recall_draft_rejects_empty_message():
    cursor = FakeCursor()

    try:
        asyncio.run(
            create_recall_draft(
                cur=cursor,
                clinic_id=uuid4(),
                patient_id=uuid4(),
                appointment_id=uuid4(),
                message="   ",
                candidate_score=55,
                match_level="secondary",
                reasons=[],
                created_by_user_id=uuid4(),
            )
        )
    except ValueError as exc:
        assert str(exc) == "Le brouillon ne peut pas être vide."
    else:
        raise AssertionError("Une ValueError était attendue.")

    assert cursor.query is None
