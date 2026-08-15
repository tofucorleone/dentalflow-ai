import asyncio
from uuid import uuid4

from app.copilot.service import create_recall_draft


class FakeCursor:
    def __init__(self):
        self.fetchone_calls = 0
        self.executed = []

        self.existing = {
            "id": uuid4(),
            "clinic_id": uuid4(),
            "patient_id": uuid4(),
            "appointment_id": uuid4(),
            "channel": "whatsapp",
            "direction": "outbound",
            "event_type": "recall_draft",
            "external_id": None,
            "payload": {
                "status": "draft",
            },
            "created_at": None,
        }

    async def execute(self, query, params):
        self.executed.append(query)

    async def fetchone(self):
        self.fetchone_calls += 1

        if self.fetchone_calls == 1:
            return self.existing

        return None


def test_existing_draft_is_reused():

    cur = FakeCursor()

    result = asyncio.run(
        create_recall_draft(
            cur=cur,
            clinic_id=cur.existing["clinic_id"],
            patient_id=cur.existing["patient_id"],
            appointment_id=cur.existing["appointment_id"],
            message="Bonjour",
            candidate_score=50,
            match_level="secondary",
            reasons=[],
            created_by_user_id=uuid4(),
        )
    )

    assert result["id"] == cur.existing["id"]

    assert len(cur.executed) == 1


def test_existing_preventive_draft_without_appointment_is_reused():
    cur = FakeCursor()

    cur.existing["appointment_id"] = None

    result = asyncio.run(
        create_recall_draft(
            cur=cur,
            clinic_id=cur.existing["clinic_id"],
            patient_id=cur.existing["patient_id"],
            appointment_id=None,
            message=(
                "Bonjour, le cabinet vous propose "
                "un contrôle de suivi."
            ),
            candidate_score=85,
            match_level="preventive",
            reasons=[
                "Dernière visite il y a plus de 24 mois",
            ],
            created_by_user_id=uuid4(),
        )
    )

    assert result["id"] == cur.existing["id"]
    assert result["appointment_id"] is None

    assert len(cur.executed) == 1

    assert (
        "appointment_id IS NOT DISTINCT FROM %s"
        in cur.executed[0]
    )
